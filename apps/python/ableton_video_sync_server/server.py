from __future__ import annotations
import sys
from pathlib import Path

from loguru import logger
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from music_video_generation.video_ingest.ingest_connector import IngestConnector
try:
    from cue_runtime import CueOutputService, RecordingCuePreviewer
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_runtime import CueOutputService, RecordingCuePreviewer
from music_video_generation.ableton.recording_state import RecordingStateStore
from music_video_generation.ableton.connection_service import AbletonConnectionService
from music_video_generation.ableton.recording_runtime import start_recording_runtime, stop_recording_runtime
from music_video_generation.postprocessing.postprocess_service import PostprocessService
from packages.python.cue_detection_service import PrimaryCueDetectionService

from music_video_generation.postprocessing.align_service import FootageAlignService
from music_video_generation.multi_video_generator.pipeline import (
    render_auto_bar_edit,
    render_sync_edit,
)
# ---- Logging setup (Loguru) ----

import sys
import logging
from pathlib import Path

from loguru import logger
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ======================================================================
# LOGGING: route stdlib logging + uvicorn logs through Loguru
# ======================================================================

# ======================================================================
# LOGGING: Loguru + bridge for stdlib + uvicorn
# ======================================================================

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / "server.log"


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Map logging level to Loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Get correct caller depth so file:line is accurate
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


def setup_logging() -> None:
    # Remove Loguru's default handler
    logger.remove()

    # Console
    logger.add(
        sys.stderr,
        level="INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # File (rotation + retention)
    logger.add(
        LOG_FILE,
        level="INFO",
        rotation="10 MB",
        retention="10 days",
        compression="zip",
        encoding="utf-8",
    )

    # Route ALL stdlib logging into Loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Specifically hook uvicorn / fastapi loggers into the bridge
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        log = logging.getLogger(name)
        log.handlers = [InterceptHandler()]
        log.propagate = False
        log.setLevel(logging.INFO)


# Call this at import time so it works with `uvicorn server:app`
setup_logging()
logger.info(f"Server booted, logging to {LOG_FILE}")


logger.add(sys.stdout, level="INFO")
logger.info("Server booted")
app = FastAPI(title="Ableton Video Sync Server", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

connector = IngestConnector()
example_cue = Path(__file__).resolve().parent / "music_video_generation" / "ableton" / "cue_refs" / "start.wav"
cue_output_service = CueOutputService(example_cue_path=example_cue)
cue_output_service.apply_saved_preferences()
recording_store = RecordingStateStore()
preview_fallback = Path(__file__).resolve().parent / "cue_refs"
recording_cue_previewer = RecordingCuePreviewer(default_cue_dir=preview_fallback)
ableton_connection_service = AbletonConnectionService()
start_recording_runtime()
postprocess_service = PostprocessService()
primary_cue_service = PrimaryCueDetectionService()
align_service = FootageAlignService()



@app.on_event("shutdown")
def _shutdown_recording_runtime():
    stop_recording_runtime()

class DeviceCreate(BaseModel):
    name: str = Field(..., description="Friendly name for the device.")
    path: str = Field(..., description="Filesystem path that should be ingested.")
    kind: str = Field(default="filesystem")
    adb_serial: str | None = Field(default=None)


class RunRequest(BaseModel):
    project_path: str = Field(..., description="Destination project directory.")
    device_ids: list[str] = Field(..., description="Device identifiers to ingest.")
    only_today: bool = Field(default=True)


class CueSpeakerSelect(BaseModel):
    device_index: int | None = Field(default=None, description="sounddevice index to use for cues.")


class CueSpeakerVolume(BaseModel):
    volume: float = Field(..., ge=0.0, description="Master gain applied to cue playback.")


class CueSpeakerTest(BaseModel):
    device_index: int | None = Field(default=None)
    volume: float | None = Field(default=None, ge=0.0)


class RecordingStateInput(BaseModel):
    project_path: str = Field(..., description="Absolute path to the active project.")
    cues_enabled: bool | None = Field(default=None)
    capture_enabled: bool | None = Field(default=None)


class RecordingCueAction(BaseModel):
    project_path: str = Field(..., description="Absolute path to the active project.")
    action: str = Field(..., description="Either 'start' or 'stop'.")

class RecordingEntryCueRequest(BaseModel):
    project_path: str = Field(..., description="Absolute path to the active project.")
    action: str = Field(..., description="Either 'start' or 'stop'.")

class PostprocessRunRequest(BaseModel):
    project_path: str = Field(..., description="Absolute path to the active project.")
    threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional override for cue match threshold (0-1).",
    )
    min_gap_s: float | None = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Optional override for minimum seconds between cue hits.",
    )
    files: list[str] | None = Field(
        default=None,
        description="Optional list of absolute media paths to reprocess.",
    )


class IngestPreviewRequest(BaseModel):
    project_path: str = Field(..., description="Absolute path to the active project.")
    device_ids: list[str] = Field(default_factory=list)
    only_today: bool = True



class AlignFootageRequest(BaseModel):
    project_path: str = Field(..., description="Absolute path to the active project.")
    audio_path: str | None = Field(
        default=None,
        description="Optional override for the soundtrack to align against.",
    )


class VideoGenSyncRequest(BaseModel):
    project_path: str = Field(..., description="Absolute path to the active project.")
    audio_path: str | None = Field(
        default=None,
        description="Optional override for the soundtrack.",
    )
    bars_per_cut: int | None = Field(
        default=None,
        ge=1,
        description="Optional bars per cut override.",
    )
    cut_length_s: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional fixed cut length override.",
    )
    custom_duration_s: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional custom total duration override.",
    )
    debug: bool | None = Field(
        default=None,
        description="Include debug overlays in the render output.",
    )


class VideoGenAutoRequest(BaseModel):
    project_path: str = Field(..., description="Absolute path to the active project.")
    video_dir: str | None = Field(
        default=None,
        description="Optional override for the footage directory.",
    )
    audio_path: str | None = Field(
        default=None,
        description="Optional override for the soundtrack.",
    )
    bars_per_cut: int | None = Field(
        default=None,
        ge=1,
        description="Optional bars per cut override.",
    )
    custom_duration_s: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional custom total duration override.",
    )


class ProjectPathRequest(BaseModel):
    project_path: str = Field(..., description="Absolute path to the active project.")


class PrimaryCueRunRequest(BaseModel):
    project_path: str = Field(..., description="Absolute path to the active project.")
    threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional override for primary cue threshold (0-1).",
    )
    min_gap_s: float | None = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Optional window between primary cue detections.",
    )
    files: list[str] | None = Field(
        default=None,
        description="Optional subset of media files to scan.",
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ingest/state")
def ingest_state() -> dict:
    return connector.export_state()


@app.get("/ingest/devices")
def list_devices() -> list[dict]:
    return connector.list_devices()


@app.get("/ingest/discovery")
def list_discovered_devices() -> list[dict]:
    return connector.list_discovered_devices()

@app.get("/ingest/discovery/{serial}/directories")
def browse_discovery_directories(serial: str, path: str | None = None) -> dict:
    try:
        return connector.browse_device_directories(serial, path)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/ingest/devices")
def add_device(payload: DeviceCreate) -> dict:
    try:
        return connector.add_device(payload.name, payload.path, kind=payload.kind, adb_serial=payload.adb_serial)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/ingest/devices/{device_id}")
def delete_device(device_id: str) -> dict:
    connector.remove_device(device_id)
    return {"status": "ok"}


@app.get("/ingest/runs")
def list_runs() -> list[dict]:
    return connector.list_runs()


@app.post("/ingest/runs")
def start_run(payload: RunRequest) -> dict:
    if not payload.device_ids:
        raise HTTPException(status_code=400, detail="Select at least one device.")

    try:
        return connector.start_run(payload.project_path, payload.device_ids, only_today=payload.only_today)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/ingest/preview")
def ingest_preview(payload: IngestPreviewRequest) -> dict:
    try:
        counts = connector.preview_counts(payload.project_path, payload.device_ids, only_today=payload.only_today)
        return {"counts": counts}
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/ingest/runs/{run_id}/abort")
def abort_run(run_id: str) -> dict:
    try:
        connector.abort_run(run_id)
        return {"status": "aborted"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/cue/speaker")
def cue_speaker_state() -> dict:
    try:
        return cue_output_service.describe()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/cue/speaker/select")
def cue_speaker_select(payload: CueSpeakerSelect) -> dict:
    try:
        return cue_output_service.update_device(payload.device_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/cue/speaker/volume")
def cue_speaker_volume(payload: CueSpeakerVolume) -> dict:
    try:
        return cue_output_service.update_volume(payload.volume)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/cue/speaker/test")
def cue_speaker_test(payload: CueSpeakerTest | None = None) -> dict:
    try:
        cue_output_service.play_example(
            device_index=payload.device_index if payload else None,
            volume=payload.volume if payload else None,
        )
        return {"status": "ok"}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/ableton/connection")
def ableton_connection_status() -> dict:
    try:
        return ableton_connection_service.status()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/ableton/connection/reconnect")
def ableton_connection_reconnect() -> dict:
    result = ableton_connection_service.request_reconnect()
    status = ableton_connection_service.status()
    payload = {**result, "status": status}
    if result.get("error"):
        raise HTTPException(status_code=500, detail=payload)
    return payload


@app.get("/recording/state")
def recording_state(project_path: str = Query(..., description="Absolute path to the active project.")) -> dict:
    try:
        return recording_store.load(project_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/recording/state")
def recording_update(payload: RecordingStateInput) -> dict:
    # cues/capture toggles move together; infer a single intent
    prefer = payload.capture_enabled if payload.capture_enabled is not None else payload.cues_enabled
    cues_enabled = prefer if prefer is not None else payload.cues_enabled
    capture_enabled = prefer if prefer is not None else payload.capture_enabled
    try:
        return recording_store.update_flags(
            payload.project_path,
            cues_enabled=cues_enabled,
            capture_enabled=capture_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/recording/state/{recording_id}")
def recording_delete(
    recording_id: str,
    project_path: str = Query(..., description="Absolute path to the active project."),
) -> dict:
    try:
        return recording_store.delete_recording(project_path, recording_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/recording/cues")
def recording_cues(payload: RecordingCueAction) -> dict:
    action = (payload.action or "").strip().lower()
    if action not in {"start", "stop"}:
        raise HTTPException(status_code=400, detail="Action must be 'start' or 'stop'.")

    try:
        state = recording_store.update_flags(
            payload.project_path,
            cue_active=True if action == "start" else False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if action == "start":
        warning = None
        try:
            cue_output_service.play_example()
        except RuntimeError as exc:
            warning = f"Unable to play cue: {exc}"
        except FileNotFoundError as exc:
            warning = str(exc)
        if warning:
            state["warning"] = warning
    return state


@app.post("/recording/state/{recording_id}/cues")
def recording_entry_cues(recording_id: str, payload: RecordingEntryCueRequest) -> dict:
    try:
        entry = recording_store.get_recording(payload.project_path, recording_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    warning = None
    try:
        recording_cue_previewer.play(entry, payload.action, project_path=payload.project_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        warning = str(exc)
    state = recording_store.load(payload.project_path)
    if warning:
        state["warning"] = warning
    return state


@app.get("/postprocess/state")
def postprocess_state(project_path: str = Query(..., description="Absolute path to the active project.")) -> dict:
    try:
        return postprocess_service.state(project_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/postprocess/run")
def postprocess_run(payload: PostprocessRunRequest) -> dict:
    try:
        return postprocess_service.start(
            payload.project_path,
            threshold=payload.threshold,
            min_gap_s=payload.min_gap_s,
            files=payload.files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/postprocess/reset")
def postprocess_reset(payload: ProjectPathRequest) -> dict:
    try:
        return postprocess_service.reset(payload.project_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/align/footage")
def align_footage(payload: AlignFootageRequest) -> dict:
    try:
        return align_service.align(payload.project_path, audio_path=payload.audio_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/align/state")
def align_state(project_path: str = Query(..., description="Absolute path to the active project.")) -> dict:
    try:
        return align_service.state(project_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


from loguru import logger

@app.post("/video-gen/sync")
def video_gen_sync(payload: VideoGenSyncRequest) -> dict:
    logger.info("video_gen_sync: payload=%r", payload)

    root = Path(payload.project_path or "").expanduser().resolve()
    if not root.exists():
        raise HTTPException(status_code=400, detail=f"Project path not found: {payload.project_path}")

    try:
        audio_path = (
            Path(payload.audio_path).expanduser().resolve()
            if payload.audio_path
            else align_service._resolve_audio(root, None)
        )
        logger.info("video_gen_sync: root=%s, audio_path=%s", root, audio_path)
    except ValueError as exc:
        logger.warning("video_gen_sync: value error while resolving audio: %r", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = render_sync_edit(
            root.name,
            audio_path,
            bars_per_cut=payload.bars_per_cut,
            cut_length_s=payload.cut_length_s,
            custom_duration_s=payload.custom_duration_s,
            debug=payload.debug,
            project_root=root,
        )
        logger.info("video_gen_sync: render_sync_edit result type=%s value=%r", type(result).__name__, result)
        return result
    except Exception as exc:
        logger.exception("video_gen_sync: render_sync_edit failed with %s", type(exc).__name__)
        # Fürs UI lieber eine generische Meldung, die interne Details nicht leakt:
        raise HTTPException(status_code=500, detail=str(exc)) from exc




@app.post("/video-gen/auto")
def video_gen_auto(payload: VideoGenAutoRequest) -> dict:
    root = Path(payload.project_path or "").expanduser().resolve()
    if not root.exists():
        raise HTTPException(status_code=400, detail=f"Project path not found: {payload.project_path}")
    try:
        audio_path = (
            Path(payload.audio_path).expanduser().resolve()
            if payload.audio_path
            else align_service._resolve_audio(root, None)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    video_dir = (
        Path(payload.video_dir).expanduser().resolve()
        if payload.video_dir
        else (root / "footage" / "videos")
    )
    if not video_dir.exists() or not video_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"Video directory not found: {video_dir}")
    try:
        return render_auto_bar_edit(
            root.name,
            video_dir,
            audio_path,
            bars_per_cut=payload.bars_per_cut,
            custom_duration_s=payload.custom_duration_s,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/primary-cues/state")
def primary_cue_state(project_path: str = Query(..., description="Absolute path to the active project.")) -> dict:
    try:
        return primary_cue_service.state(project_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/primary-cues/run")
def primary_cue_run(payload: PrimaryCueRunRequest) -> dict:
    try:
        return primary_cue_service.start(
            payload.project_path,
            threshold=payload.threshold,
            min_gap_s=payload.min_gap_s,
            files=payload.files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc



@app.post("/primary-cues/reset")
def primary_cue_reset(payload: ProjectPathRequest) -> dict:
    try:
        return primary_cue_service.reset(payload.project_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def run() -> None:
    uvicorn.run("server:app", host="127.0.0.1", port=5050, reload=False)


if __name__ == "__main__":
    run()
