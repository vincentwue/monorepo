from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import uuid4


class RecordingStateStore:
    """Lightweight JSON-backed state for cue/record controls per project."""

    FILENAME = "recordings.json"

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ helpers
    def _default_state(self) -> Dict[str, Any]:
        return {
            "cues_enabled": True,
            "capture_enabled": True,
            "cue_active": False,
            "recordings": [],
            "last_updated": datetime.now(UTC).isoformat(),
        }

    def _resolve_project(self, project_path: str) -> Path:
        project = Path(project_path or "").expanduser().resolve()
        if not project.exists() or not project.is_dir():
            raise ValueError(f"Project path not found: {project_path}")
        return project

    def _find_state_root(self, start: Path) -> Path:
        current = start
        while True:
            candidate = current / self.FILENAME
            if candidate.exists():
                return current
            if current.parent == current:
                break
            current = current.parent
        return start

    def _state_file(self, project: Path) -> Path:
        return project / self.FILENAME

    def _read_state(self, project: Path) -> Tuple[Dict[str, Any], str | None]:
        path = self._state_file(project)
        if not path.exists():
            return {}, None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}, None
        except json.JSONDecodeError:
            warning = f"Unable to parse {path.name}. Starting with a fresh state."
            return {}, warning

    def _write_state(self, project: Path, data: Dict[str, Any]) -> None:
        path = self._state_file(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _apply_defaults(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        state = self._default_state()
        mutated = False
        if not isinstance(data, dict):
            return state, True
        for key in ("cues_enabled", "capture_enabled", "cue_active", "last_updated"):
            if key in data:
                state[key] = data[key]
        cleaned: List[Dict[str, Any]] = []
        if isinstance(data.get("recordings"), list):
            for entry in data["recordings"]:
                if not isinstance(entry, dict):
                    mutated = True
                    continue
                if not isinstance(entry.get("id"), str) or not entry["id"]:
                    entry["id"] = uuid4().hex
                    mutated = True
                cleaned.append(entry)
        else:
            mutated = True
        state["recordings"] = cleaned
        return state, mutated

    def _prepare_response(self, project: Path, state: Dict[str, Any], warning: str | None) -> Dict[str, Any]:
        payload = dict(state)
        payload["project_path"] = str(project)
        if warning:
            payload["warning"] = warning
        return payload

    # ------------------------------------------------------------------ public API
    def _resolve_root(self, project_path: str) -> Path:
        base = self._resolve_project(project_path)
        return self._find_state_root(base)

    def load(self, project_path: str) -> Dict[str, Any]:
        project = self._resolve_root(project_path)
        with self._lock:
            raw, warning = self._read_state(project)
            state, mutated = self._apply_defaults(raw)
            if mutated:
                self._write_state(project, state)
        return self._prepare_response(project, state, warning)

    def update_flags(
        self,
        project_path: str,
        *,
        cues_enabled: bool | None = None,
        capture_enabled: bool | None = None,
        cue_active: bool | None = None,
    ) -> Dict[str, Any]:
        project = self._resolve_root(project_path)
        with self._lock:
            raw, _warning = self._read_state(project)
            state, _ = self._apply_defaults(raw)
            if cues_enabled is not None:
                state["cues_enabled"] = cues_enabled
            if capture_enabled is not None:
                state["capture_enabled"] = capture_enabled
            if cue_active is not None:
                state["cue_active"] = cue_active
            state["last_updated"] = datetime.now(UTC).isoformat()
            self._write_state(project, state)
        return self._prepare_response(project, state, None)

    def append_recording(self, project_path: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        project = self._resolve_root(project_path)
        with self._lock:
            raw, _warning = self._read_state(project)
            state, _ = self._apply_defaults(raw)
            if not isinstance(state["recordings"], list):
                state["recordings"] = []
            payload = dict(entry)
            if not isinstance(payload.get("id"), str) or not payload["id"]:
                payload["id"] = uuid4().hex
            state["recordings"].append(payload)
            state["last_updated"] = datetime.now(UTC).isoformat()
            self._write_state(project, state)
        return self._prepare_response(project, state, None)

    def get_recording(self, project_path: str, recording_id: str) -> Dict[str, Any]:
        if not recording_id:
            raise ValueError("Recording id is required.")
        project = self._resolve_root(project_path)
        with self._lock:
            raw, _warning = self._read_state(project)
            state, _ = self._apply_defaults(raw)
            recordings: List[Dict[str, Any]] = state.get("recordings", [])
            for entry in recordings:
                if entry.get("id") == recording_id:
                    return dict(entry)
        raise ValueError(f"Recording not found: {recording_id}")

    def delete_recording(self, project_path: str, recording_id: str) -> Dict[str, Any]:
        if not recording_id:
            raise ValueError("Recording id is required.")
        project = self._resolve_root(project_path)
        with self._lock:
            raw, _warning = self._read_state(project)
            state, _ = self._apply_defaults(raw)
            recordings: List[Dict[str, Any]] = state.get("recordings", [])
            before = len(recordings)
            state["recordings"] = [rec for rec in recordings if rec.get("id") != recording_id]
            if before == len(state["recordings"]):
                raise ValueError(f"Recording not found: {recording_id}")
            state["last_updated"] = datetime.now(UTC).isoformat()
            self._write_state(project, state)
        return self._prepare_response(project, state, None)


__all__ = ["RecordingStateStore"]
