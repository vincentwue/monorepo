from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any, Dict

from packages.python.live_rpyc.live_client import LiveClient

logger = logging.getLogger(__name__)


class AbletonConnectionService:
    """Expose simple status/reconnect helpers for Ableton Live."""

    def __init__(self) -> None:
        self._reconnect_lock = threading.Lock()
        self._reconnect_thread: threading.Thread | None = None

    # ------------------------------------------------------------------ helpers
    def _client(self) -> LiveClient:
        return LiveClient.get_instance()

    def _is_reconnecting(self) -> bool:
        thread = self._reconnect_thread
        return bool(thread and thread.is_alive())

    def _format_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload.setdefault("timestamp", datetime.now(UTC).isoformat())
        payload["reconnecting"] = self._is_reconnecting()
        return payload

    # ------------------------------------------------------------------ public API
    def status(self) -> Dict[str, Any]:
        try:
            client = self._client()
        except Exception as exc:
            logger.warning("Ableton Live client unavailable: %s", exc)
            return self._format_response(
                {
                    "connected": False,
                    "project_saved": False,
                    "project_path": None,
                    "project_name": None,
                    "error": str(exc),
                }
            )

        response: Dict[str, Any] = {
            "connected": False,
            "project_saved": False,
            "project_path": None,
            "project_name": None,
            "is_playing": None,
            "tempo": None,
            "warning": None,
            "error": None,
        }

        try:
            response["connected"] = bool(client.is_connected())
        except Exception as exc:
            response["error"] = f"is_connected failed: {exc}"
            logger.debug("is_connected failed: %s", exc)

        try:
            song = getattr(client, "song", None)
            if song is not None:
                name = str(getattr(song, "name", "") or "")
                path = str(getattr(song, "file_path", "") or "")
                response["project_name"] = name or None
                response["project_path"] = path or None
                response["project_saved"] = bool(path)
                tempo = getattr(song, "tempo", None)
                response["tempo"] = float(tempo) if tempo is not None else None
                response["is_playing"] = bool(getattr(song, "is_playing", False))
                if not response["project_saved"]:
                    response["warning"] = "Ableton project is not saved. Save before recording."
            elif response["connected"]:
                response["warning"] = "Connected to Live but no song document is available."
        except Exception as exc:
            response["error"] = f"Failed to read song info: {exc}"
            logger.warning("Failed to gather Ableton song info: %s", exc)

        return self._format_response(response)

    def _manual_reconnect(self, client: LiveClient, attempts: int = 3, backoff: float = 5.0) -> bool:
        """
        Attempt to reconnect to Ableton Live with a few retries/backoff.
        Returns True if connection looks healthy afterwards.
        """
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                time.sleep(backoff)
            try:
                logger.info("Manual reconnect attempt #%s ...", attempt)
                try:
                    client._cleanup_connection()  # type: ignore[attr-defined]
                except Exception:
                    pass
                client._connect()  # type: ignore[attr-defined]
                if not client._conn:  # type: ignore[attr-defined]
                    logger.debug("Manual reconnect attempt #%s did not yield a connection.", attempt)
                    continue
                try:
                    client._rebind_all_listeners()  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    client.refresh_dynamic_methods()
                except Exception:
                    pass
                if client.on_reconnected:
                    try:
                        client.on_reconnected()
                    except Exception:
                        pass
                logger.info("Manual Ableton reconnect succeeded.")
                return True
            except Exception as exc:
                logger.warning("Manual reconnect attempt #%s failed: %s", attempt, exc)
        return False

    def request_reconnect(self) -> Dict[str, Any]:
        try:
            client = self._client()
        except Exception as exc:
            logger.error("Unable to load Live client for reconnect: %s", exc)
            return {
                "started": False,
                "already_running": False,
                "reconnecting": self._is_reconnecting(),
                "error": str(exc),
            }

        with self._reconnect_lock:
            if self._is_reconnecting():
                return {
                    "started": False,
                    "already_running": True,
                    "reconnecting": True,
                }

            def _worker():
                success = self._manual_reconnect(client)
                if not success:
                    logger.warning("Manual reconnect attempt failed. Background monitor will keep retrying.")

            def _run_and_reset():
                try:
                    success = self._manual_reconnect(client)
                    if not success:
                        logger.warning("Manual reconnect attempts exhausted. Background monitor will continue retrying.")
                finally:
                    self._reconnect_thread = None

            self._reconnect_thread = threading.Thread(target=_run_and_reset, daemon=True)
            self._reconnect_thread.start()
            return {
                "started": True,
                "already_running": False,
                "reconnecting": True,
            }


__all__ = ["AbletonConnectionService"]
