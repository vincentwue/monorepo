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


# ---------------------------------------------------------
# Global runtime variables
# ---------------------------------------------------------

_runtime_lock = threading.Lock()

# Must always exist at module import time
_runtime_thread: Optional[threading.Thread] = None
_runtime_stop_event: Optional[threading.Event] = None


# ---------------------------------------------------------
# Internal runtime loop
# ---------------------------------------------------------

def _run():
    """
    This runs in the background thread and handles the LiveClient event loop.
    It will exit once LiveClient.stop() is called.
    """
    client = LiveClient.get_instance()
    rm = RecordingManager.instance()

    if insert_ableton_recording is not None:
        rm.add_on_record_end_listener(insert_ableton_recording)
    else:
        logger.warning(
            "Mongo integration disabled (bson import failed: %s). "
            "Recordings will not sync.",
            _IMPORT_ERROR
        )

    logger.info("Recording runtime started (LiveClient + RecordingManager).")

    try:
        client.run_forever()
    except Exception:
        logger.exception("Recording runtime encountered an exception.")
    finally:
        logger.info("Recording runtime stopped.")


# ---------------------------------------------------------
# API: start / stop
# ---------------------------------------------------------

def start_recording_runtime() -> None:
    """
    Starts the Ableton Recording Runtime thread.
    Safe to call multiple times.
    """
    global _runtime_thread, _runtime_stop_event

    with _runtime_lock:
        if _runtime_thread is not None and _runtime_thread.is_alive():
            logger.info("start_recording_runtime: runtime already active.")
            return

        logger.info("start_recording_runtime: starting recording runtime thread.")

        # New stop event for this runtime session
        _runtime_stop_event = threading.Event()

        # New thread
        _runtime_thread = threading.Thread(
            target=_run,
            name="recording-runtime",
            daemon=True,
        )
        _runtime_thread.start()


def stop_recording_runtime() -> None:
    """
    Stops the Ableton Recording Runtime thread.
    Safe to call multiple times. Never raises.

    This shutdown is done by signalling LiveClient.stop(),
    then joining the thread shortly.
    """
    global _runtime_thread, _runtime_stop_event

    with _runtime_lock:
        if _runtime_thread is None:
            logger.info("stop_recording_runtime: no active runtime thread.")
            return

        if not _runtime_thread.is_alive():
            logger.info("stop_recording_runtime: thread already dead.")
            _runtime_thread = None
            _runtime_stop_event = None
            return

        logger.info("stop_recording_runtime: signalling LiveClient to stop...")

        # Try stopping the Live client cleanly
        try:
            LiveClient.get_instance().stop()
        except Exception:
            logger.exception("stop_recording_runtime: LiveClient.stop() failed.")

        # Join the thread with timeout
        try:
            _runtime_thread.join(timeout=5.0)
            if _runtime_thread.is_alive():
                logger.warning("stop_recording_runtime: runtime thread did not exit within timeout.")
            else:
                logger.info("stop_recording_runtime: runtime thread cleanly stopped.")
        except Exception:
            logger.exception("stop_recording_runtime: thread join failed.")

        # Clear references so next runtime starts fresh
        _runtime_thread = None
        _runtime_stop_event = None


__all__ = ["start_recording_runtime", "stop_recording_runtime"]
