from __future__ import annotations

import threading
from typing import Optional

from loguru import logger

from music_video_generation.ableton.recording_manager import RecordingManager
from packages.python.live_rpyc.live_client import LiveClient

try:
    from music_video_generation.ableton.ableton_insert_recordings_to_db import insert_ableton_recording
except ImportError as exc:
    insert_ableton_recording = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

_runtime_lock = threading.Lock()
_runtime_thread: Optional[threading.Thread] = None
_runtime_stop = threading.Event()


def _run():
    client = LiveClient.get_instance()
    rm = RecordingManager.instance()
    if insert_ableton_recording is not None:
        rm.add_on_record_end_listener(insert_ableton_recording)
    else:
        logger.warning("Mongo integration disabled (bson import failed: %s). Recordings will not sync.", _IMPORT_ERROR)
    logger.info("Recording runtime started (LiveClient + RecordingManager).")
    try:
        client.run_forever()
    finally:
        logger.info("Recording runtime stopped.")


def start_recording_runtime() -> None:
    global _runtime_thread
    with _runtime_lock:
        if _runtime_thread and _runtime_thread.is_alive():
            return
        _runtime_stop.clear()
        _runtime_thread = threading.Thread(target=_run, name="recording-runtime", daemon=True)
        _runtime_thread.start()


def stop_recording_runtime() -> None:
    with _runtime_lock:
        if _runtime_thread and _runtime_thread.is_alive():
            try:
                LiveClient.get_instance().stop()
            except Exception:
                pass
        _runtime_thread = None


__all__ = ["start_recording_runtime", "stop_recording_runtime"]
