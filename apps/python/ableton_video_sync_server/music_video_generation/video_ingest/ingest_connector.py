from __future__ import annotations

import json
from loguru import logger
import shlex
import subprocess
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, time
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Tuple

from .ingest import ingest as run_ingest, preview_ingest_counts
from .models import StateStore, VideoSource

DEFAULT_STATE_FILE = Path(__file__).with_name("video_ingest_state.json")
DEFAULT_DISCOVERY_FILE = Path(__file__).with_name(".video_ingest_state.json")

ANDROID_DEFAULT_CAMERA_PATHS = [
  "/storage/emulated/0/DCIM/Camera",
  "/storage/emulated/0/DCIM/OpenCamera",
  "/sdcard/DCIM/Camera",
  "/sdcard/DCIM/OpenCamera",
]


def _now() -> datetime:
  return datetime.now(UTC)


def _start_of_today() -> datetime:
  today = datetime.now(UTC).date()
  return datetime.combine(today, time.min, tzinfo=UTC)


@dataclass
class Device:
  id: str
  name: str
  kind: str
  path: str
  adb_serial: Optional[str] = None
  created_at: str = field(default_factory=lambda: _now().isoformat())
  last_ingested_at: Optional[str] = None


@dataclass
class IngestRun:
  id: str
  project_path: str
  device_ids: List[str]
  status: str = "pending"
  copied_files: List[str] = field(default_factory=list)
  error: Optional[str] = None
  started_at: str = field(default_factory=lambda: _now().isoformat())
  completed_at: Optional[str] = None
  only_today: bool = True


class IngestConnector:
  """JSON backed ingest storage and execution helper."""

  def __init__(self, state_path: Path | str | None = None, discovery_path: Path | str | None = None) -> None:
    self.state_path = Path(state_path) if state_path else DEFAULT_STATE_FILE
    self.discovery_path = Path(discovery_path) if discovery_path else DEFAULT_DISCOVERY_FILE
    self.state_path.parent.mkdir(parents=True, exist_ok=True)
    self._lock = threading.Lock()
    self._run_threads: Dict[str, threading.Thread] = {}
    self._run_events: Dict[str, threading.Event] = {}
    if not self.state_path.exists():
      self._write_state({"devices": [], "runs": []})

  # ---------------------------------------------------------------------------
  # Persistence helpers
  # ---------------------------------------------------------------------------
  def _read_state(self) -> Dict[str, List[Dict]]:
    if not self.state_path.exists():
      return {"devices": [], "runs": []}
    with self.state_path.open("r", encoding="utf-8") as handle:
      return json.load(handle)

  def _write_state(self, data: Dict[str, Iterable[Dict]]) -> None:
    tmp_path = self.state_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
      json.dump(data, handle, indent=2)
    tmp_path.replace(self.state_path)

  def _mutate_state(self, mutator):
    with self._lock:
      state = self._read_state()
      mutator(state)
      self._write_state(state)
      return state

  def _read_discovery(self) -> Dict[str, Dict]:
    if not self.discovery_path.exists():
      return {}
    try:
      with self.discovery_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
    except json.JSONDecodeError:
      return {}

  def _suggest_remote_path(self, label: Optional[str]) -> Optional[str]:
    if not label:
      return None
    state = self._read_discovery()
    for key in state.keys():
      parts = key.split(":", 2)
      if len(parts) == 3 and parts[0] == "adb":
        device_label = parts[1]
        if device_label.lower() == label.lower():
          return parts[2]
    return None

  # ---------------------------------------------------------------------------
  # Public API
  # ---------------------------------------------------------------------------
  def export_state(self) -> Dict[str, List[Dict]]:
    return self._read_state()

  def list_devices(self) -> List[Dict]:
    return self._read_state().get("devices", [])

  def list_runs(self) -> List[Dict]:
    return self._read_state().get("runs", [])

  def list_discovered_devices(self) -> List[Dict]:
    return self._discover_adb_devices()

  def add_device(self, name: str, path: str, kind: str = "filesystem", adb_serial: str | None = None) -> Dict:
    if not name.strip():
      raise ValueError("Device name cannot be empty.")

    if kind == "adb":
      normalized_path = path.strip()
      if not normalized_path:
        raise ValueError("Provide a remote folder path for your Android device (e.g. /storage/emulated/0/DCIM/Camera).")
    else:
      normalized_path = str(Path(path).expanduser())
      if not Path(normalized_path).exists():
        raise FileNotFoundError(f"Device path '{normalized_path}' does not exist.")

    device = Device(
      id=str(uuid.uuid4()),
      name=name.strip(),
      kind=kind or "filesystem",
      path=normalized_path,
      adb_serial=adb_serial.strip() if adb_serial else None,
    )

    def mutator(state):
      devices = state.setdefault("devices", [])
      devices.append(asdict(device))

    self._mutate_state(mutator)
    return asdict(device)

  def remove_device(self, device_id: str) -> None:
    def mutator(state):
      state["devices"] = [device for device in state.get("devices", []) if device.get("id") != device_id]

    self._mutate_state(mutator)

  def start_run(self, project_path: str, device_ids: List[str], only_today: bool = True) -> Dict:
    resolved_project = Path(project_path).expanduser()
    if not resolved_project.exists():
      raise FileNotFoundError(f"Project path '{resolved_project}' does not exist.")

    devices = {device["id"]: device for device in self.list_devices()}
    missing_devices = [device_id for device_id in device_ids if device_id not in devices]
    if missing_devices:
      raise ValueError(f"Unknown devices: {', '.join(missing_devices)}")

    run = IngestRun(
      id=str(uuid.uuid4()),
      project_path=str(resolved_project),
      device_ids=device_ids,
      status="running",
      only_today=only_today,
    )
    self._mutate_state(lambda state: state.setdefault("runs", []).append(asdict(run)))
    logger.info(
      "[ingest] Starting run %s for project %s with devices=%s only_today=%s",
      run.id,
      resolved_project,
      device_ids,
      only_today,
    )

    base_output_dir = resolved_project / "footage" / "videos"
    base_output_dir.mkdir(parents=True, exist_ok=True)
    sources: List[VideoSource] = []
    for device_id in device_ids:
      device = devices[device_id]
      source_kind = device.get("kind") or "filesystem"
      source_path = device.get("path")
      if not source_path:
        raise ValueError(f"Device '{device['name']}' is missing a source path.")
      logger.info(
        "[ingest] Using source %s kind=%s path=%s adb_serial=%s",
        device_id,
        source_kind,
        source_path,
        device.get("adb_serial"),
      )
      sources.append(
        VideoSource(
          path=source_path,
          device_name=device["name"],
          kind=source_kind,
          adb_serial=device.get("adb_serial"),
        )
      )

    state_store = StateStore(self.discovery_path)
    stop_event = threading.Event()
    self._run_events[run.id] = stop_event

    def _worker():
      try:
        copied_paths = run_ingest(
          sources=sources,
          base_output_dir=base_output_dir,
          state=state_store,
          only_today=only_today,
          stop_event=stop_event,
        )
        copied_files = [str(path) for path in copied_paths]
        if stop_event.is_set():
          logger.info("[ingest] Run %s aborted. Copied %d file(s).", run.id, len(copied_files))
          self._update_run(run.id, status="aborted", copied_files=copied_files, error="Aborted by user")
        else:
          logger.info("[ingest] Run %s completed. Copied %d file(s).", run.id, len(copied_files))
          self._mark_devices_ingested(device_ids)
          self._update_run(run.id, status="completed", copied_files=copied_files, error=None)
      except Exception as exc:
        logger.exception("[ingest] Run %s failed: %s", run.id, exc)
        self._update_run(run.id, status="failed", error=str(exc))
      finally:
        self._run_events.pop(run.id, None)
        self._run_threads.pop(run.id, None)

    thread = threading.Thread(target=_worker, name=f"ingest-run-{run.id}", daemon=True)
    self._run_threads[run.id] = thread
    thread.start()

    final_state = self._read_state()
    return next(run_obj for run_obj in final_state.get("runs", []) if run_obj["id"] == run.id)

  # ---------------------------------------------------------------------------
  # Internal helpers
  # ---------------------------------------------------------------------------
  def _update_run(self, run_id: str, **updates) -> None:
    def mutator(state):
      for run in state.get("runs", []):
        if run.get("id") == run_id:
          run.update(updates)
          if updates.get("status") in {"completed", "failed"}:
            run["completed_at"] = _now().isoformat()

    self._mutate_state(mutator)

  def _mark_devices_ingested(self, device_ids: List[str]) -> None:
    def mutator(state):
      for entry in state.get("devices", []):
        if entry.get("id") in device_ids:
          entry["last_ingested_at"] = _now().isoformat()

    self._mutate_state(mutator)

  def abort_run(self, run_id: str) -> None:
    event = self._run_events.get(run_id)
    if not event:
      raise ValueError(f"Run {run_id} is not running.")
    event.set()
    logger.info("[ingest] Abort requested for run %s", run_id)

  def preview_counts(self, project_path: str, device_ids: List[str], only_today: bool = True) -> Dict[str, Dict[str, int]]:
    resolved_project = Path(project_path).expanduser()
    if not resolved_project.exists():
      raise FileNotFoundError(f"Project path '{resolved_project}' does not exist.")

    devices = {device["id"]: device for device in self.list_devices()}
    missing_devices = [device_id for device_id in device_ids if device_id not in devices]
    if missing_devices:
      raise ValueError(f"Unknown devices: {', '.join(missing_devices)}")

    sources: List[VideoSource] = []
    for device_id in device_ids:
      device = devices[device_id]
      source_kind = device.get("kind") or "filesystem"
      source_path = device.get("path")
      if not source_path:
        raise ValueError(f"Device '{device['name']}' is missing a source path.")
      sources.append(
        VideoSource(
          path=source_path,
          device_name=device["name"],
          kind=source_kind,
          adb_serial=device.get("adb_serial"),
        )
      )

    state_store = StateStore(self.discovery_path)
    summary = preview_ingest_counts(sources, state=state_store, only_today=only_today)
    logger.info("[ingest] Preview counts for project %s: %s", resolved_project, summary)
    return {
      device_id: summary.get(devices[device_id]["name"], {"total": 0, "new": 0})
      for device_id in device_ids
    }

  def _normalize_remote_path(self, candidate: Optional[str]) -> str:
    raw = (candidate or "").strip()
    base = raw or "/"
    normalized = base.replace("\\", "/")
    if not normalized.startswith("/"):
      normalized = f"/{normalized}"
    while "//" in normalized:
      normalized = normalized.replace("//", "/")
    if normalized != "/" and normalized.endswith("/"):
      normalized = normalized.rstrip("/")
    return normalized or "/"

  def _default_directory_roots(self) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = [
      {
        "path": "/",
        "name": "/",
        "hasChildren": True,
      }
    ]
    seen = {"/"}
    for candidate in ANDROID_DEFAULT_CAMERA_PATHS:
      normalized = self._normalize_remote_path(candidate)
      if normalized in seen:
        continue
      if normalized == "/":
        display_name = "/"
      else:
        segments = [segment for segment in normalized.rstrip("/").split("/") if segment]
        if not segments:
          display_name = normalized
        elif len(segments) == 1:
          display_name = segments[0]
        else:
          display_name = "/".join(segments[-2:])
      entries.append(
        {
          "path": normalized,
          "name": display_name,
          "hasChildren": True,
        }
      )
      seen.add(normalized)
    return entries

  def _remote_parent_path(self, path: str) -> Optional[str]:
    if path == "/":
      return None
    parent = str(PurePosixPath(path).parent)
    if parent == path or parent == ".":
      return None
    return parent or "/"

  def _run_adb_shell(self, serial: Optional[str], command: str) -> subprocess.CompletedProcess:
    base = ["adb"]
    if serial:
      base += ["-s", serial]
    base += ["shell", command]
    try:
      return subprocess.run(base, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
      raise FileNotFoundError("adb executable not found on PATH. Install platform-tools to browse Android folders.") from exc

  def _list_remote_directories(self, serial: str, remote_path: str) -> List[str]:
    normalized = remote_path or "/"
    normalized = normalized if normalized != "" else "/"
    quoted = shlex.quote(normalized)
    try:
      result = self._run_adb_shell(serial, f"toybox ls -1p {quoted}")
    except subprocess.CalledProcessError as exc:
      stderr = exc.stderr.strip()
      stdout = exc.stdout.strip()
      message = stderr or stdout or f"Unable to browse {normalized}"
      raise RuntimeError(message) from exc

    entries: List[str] = []
    for line in result.stdout.splitlines():
      entry = line.strip()
      if not entry or entry in {".", ".."}:
        continue
      if entry.endswith("/"):
        name = entry.rstrip("/")
        if normalized == "/":
          entries.append(f"/{name}")
        else:
          merged = f"{normalized}/{name}"
          while "//" in merged:
            merged = merged.replace("//", "/")
          entries.append(merged)
    deduped = sorted({value for value in entries})
    return deduped

  def browse_device_directories(self, serial: str, path: Optional[str] = None) -> Dict:
    serial_value = (serial or "").strip()
    if not serial_value:
      raise ValueError("Provide a device serial to browse directories.")

    if path is None:
      return {
        "serial": serial_value,
        "path": None,
        "parent": None,
        "entries": self._default_directory_roots(),
      }

    target_path = self._normalize_remote_path(path)
    directories = self._list_remote_directories(serial_value, target_path)
    entries = [
      {
        "path": entry,
        "name": entry.rstrip("/").split("/")[-1] or entry,
        "hasChildren": True,
      }
      for entry in directories
    ]

    return {
      "serial": serial_value,
      "path": target_path,
      "parent": self._remote_parent_path(target_path),
      "entries": entries,
    }

  def _parse_discovery_key(self, key: str) -> Tuple[str, str, Optional[str]]:
    parts = key.split(":", 2)
    if len(parts) == 3:
      return parts[0], parts[1], parts[2]
    if len(parts) == 2:
      return parts[0], parts[1], None
    return parts[0], key, None

  def _discover_adb_devices(self) -> List[Dict]:
    try:
      output = subprocess.run(
        ["adb", "devices", "-l"],
        check=True,
        capture_output=True,
        text=True,
      )
    except FileNotFoundError:
      logger.debug("adb executable not found on PATH.")
      return []
    except subprocess.CalledProcessError as exc:
      logger.warning("adb devices command failed: %s", exc.stderr.strip())
      return []

    registered_serials = {
      (device.get("adb_serial") or "").lower()
      for device in self.list_devices()
      if device.get("adb_serial")
    }

    suggestions = []
    lines = [line.strip() for line in output.stdout.splitlines() if line.strip()]
    for line in lines:
      if line.lower().startswith("list of devices"):
        continue
      parts = line.split()
      if not parts:
        continue
      serial = parts[0]
      if serial.lower() in registered_serials:
        continue
      state = parts[1] if len(parts) > 1 else "unknown"
      extras: Dict[str, str] = {}
      for token in parts[2:]:
        if ":" in token:
          key, value = token.split(":", 1)
          extras[key] = value
      label = extras.get("model") or extras.get("device") or serial
      suggested_path = self._suggest_remote_path(label) or ANDROID_DEFAULT_CAMERA_PATHS[0]
      suggestions.append(
        {
          "id": f"adb:{serial}",
          "kind": "adb",
          "label": label,
          "serial": serial,
          "path": suggested_path,
          "connection_state": self._map_adb_state(state),
          "status_text": state,
          "hints": self._state_hints(state),
        }
      )

    return suggestions

  @staticmethod
  def _map_adb_state(raw: str) -> str:
    normalized = raw.strip().lower()
    if normalized == "device":
      return "ready"
    if normalized in {"unauthorized", "authorizing"}:
      return "needs_permission"
    if normalized == "offline":
      return "offline"
    return "unknown"

  @staticmethod
  def _state_hints(state: str) -> List[str]:
    normalized = state.strip().lower()
    if normalized in {"unauthorized", "authorizing"}:
      return [
        "Unlock the phone and accept the USB debugging prompt.",
        "Ensure developer options and USB debugging are enabled.",
      ]
    if normalized == "offline":
      return ["Reconnect the USB cable and ensure the device is awake."]
    return []


__all__ = ["IngestConnector", "Device", "IngestRun"]
