from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Optional

import requests
from PySide6 import QtCore, QtGui, QtWidgets

from utils import log


JSON_RESPONSE_INSTRUCTIONS = """\
You are an engineering assistant. Respond EXACTLY with JSON using this structure:
{
  "steps": ["text summary per step"],
  "files": [
    {
      "path": "relative/or/absolute/path",
      "operation": "create|update|delete",
      "language": "python|typescript|... or omit if unknown",
      "content": "full file content when creating/updating"
    }
  ],
  "notes": "plain text answer or clarifications (required even when empty)."
}
If no file changes are needed, return "files": [] but still include an informative "notes".
"""


class PromptPanelMixin:
    """Encapsulates the assistant prompt UI panel and network workflow."""

    def _init_prompt_panel_state(self) -> None:
        self.prompt_editor: Optional[QtWidgets.QPlainTextEdit] = None
        self.prompt_output: Optional[QtWidgets.QPlainTextEdit] = None
        self.prompt_structured_text: Optional[QtWidgets.QPlainTextEdit] = None
        self.prompt_send_button: Optional[QtWidgets.QPushButton] = None
        self.prompt_abort_button: Optional[QtWidgets.QPushButton] = None
        self.prompt_apply_button: Optional[QtWidgets.QPushButton] = None
        self.prompt_status: Optional[QtWidgets.QLabel] = None
        self.prompt_save_timer = QtCore.QTimer(self)
        self.prompt_save_timer.setSingleShot(True)
        self.prompt_save_timer.timeout.connect(self._persist_prompt_text)
        self.active_prompt_thread: Optional[threading.Thread] = None
        self.prompt_token_counter = 0
        self.prompt_current_token: Optional[int] = None
        self.prompt_aborted_tokens: set[int] = set()
        self.current_prompt_abort_event: Optional[threading.Event] = None
        self.prompt_last_structured: Optional[dict] = None
        self.repo_root = self._detect_repo_root()

    # ------------------------------------------------------------------ UI
    def _build_prompt_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(QtWidgets.QLabel("Assistant Prompt"))

        self.prompt_editor = QtWidgets.QPlainTextEdit()
        self.prompt_editor.setFont(self._monospace_font())
        stored_prompt = self.settings.value("prompt/text", "", str)
        if stored_prompt:
            self.prompt_editor.setPlainText(stored_prompt)
        self.prompt_editor.textChanged.connect(self._handle_prompt_text_changed)
        layout.addWidget(self.prompt_editor, 1)

        controls = QtWidgets.QHBoxLayout()
        self.prompt_send_button = QtWidgets.QPushButton("Send Prompt")
        self.prompt_send_button.clicked.connect(self.send_prompt)
        controls.addWidget(self.prompt_send_button, 0)

        self.prompt_abort_button = QtWidgets.QPushButton("Abort")
        self.prompt_abort_button.setEnabled(False)
        self.prompt_abort_button.clicked.connect(self.abort_prompt)
        controls.addWidget(self.prompt_abort_button, 0)

        self.prompt_status = QtWidgets.QLabel("")
        self.prompt_status.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        controls.addWidget(self.prompt_status, 1)
        layout.addLayout(controls)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.setChildrenCollapsible(False)

        raw_panel = QtWidgets.QWidget()
        raw_layout = QtWidgets.QVBoxLayout(raw_panel)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        raw_layout.addWidget(QtWidgets.QLabel("Raw Output"))
        self.prompt_output = QtWidgets.QPlainTextEdit()
        self.prompt_output.setReadOnly(True)
        self.prompt_output.setFont(self._monospace_font())
        raw_layout.addWidget(self.prompt_output, 1)
        split.addWidget(raw_panel)

        structured_panel = QtWidgets.QWidget()
        struct_layout = QtWidgets.QVBoxLayout(structured_panel)
        struct_layout.setContentsMargins(0, 0, 0, 0)
        struct_layout.addWidget(QtWidgets.QLabel("Structured Result"))
        self.prompt_structured_text = QtWidgets.QPlainTextEdit()
        self.prompt_structured_text.setReadOnly(True)
        self.prompt_structured_text.setFont(self._monospace_font())
        struct_layout.addWidget(self.prompt_structured_text, 2)

        struct_layout.addWidget(QtWidgets.QLabel("Proposed Files"))
        self.files_table = QtWidgets.QTableWidget(0, 3)
        self.files_table.setHorizontalHeaderLabels(["Path", "Op", "Preview"])
        header = self.files_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.files_table.verticalHeader().setVisible(False)
        self.files_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.files_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        struct_layout.addWidget(self.files_table, 3)

        self.prompt_apply_button = QtWidgets.QPushButton("Apply File Changes")
        self.prompt_apply_button.setEnabled(False)
        self.prompt_apply_button.clicked.connect(self.apply_structured_changes)
        struct_layout.addWidget(self.prompt_apply_button, 0)
        split.addWidget(structured_panel)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)

        layout.addWidget(split, 1)

        return panel

    # --------------------------------------------------------- persistence
    def _handle_prompt_text_changed(self) -> None:
        if self.prompt_save_timer.isActive():
            self.prompt_save_timer.stop()
        self.prompt_save_timer.start(600)

    def _persist_prompt_text(self) -> None:
        if not self.prompt_editor:
            return
        text = self.prompt_editor.toPlainText()
        self.settings.setValue("prompt/text", text)

    # ------------------------------------------------------------- actions
    def send_prompt(self) -> None:
        if self.active_prompt_thread and self.active_prompt_thread.is_alive():
            if not (self.current_prompt_abort_event and self.current_prompt_abort_event.is_set()):
                self.show_info("Prompt request already running.", duration=2)
                return
        if not self.prompt_editor:
            return
        base_prompt = self.prompt_editor.toPlainText().strip()
        if not base_prompt:
            self.show_info("Enter a prompt before sending.", duration=3)
            return
        prompt = self._compose_prompt_with_context(base_prompt)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            self.show_info("OPENAI_API_KEY environment variable is not set.", duration=4)
            return

        if self.prompt_output:
            self.prompt_output.clear()
        if self.prompt_structured_text:
            self.prompt_structured_text.setPlainText("Awaiting response...")
        self.prompt_last_structured = None
        if self.prompt_apply_button:
            self.prompt_apply_button.setEnabled(False)
        self._clear_files_table()
        self._clear_files_table()
        if self.prompt_send_button:
            self.prompt_send_button.setEnabled(False)
        if self.prompt_abort_button:
            self.prompt_abort_button.setEnabled(True)
        if self.prompt_status:
            self.prompt_status.setText("Sending...")

        abort_event = threading.Event()
        self.current_prompt_abort_event = abort_event
        self.prompt_token_counter += 1
        token = self.prompt_token_counter
        self.prompt_current_token = token
        self.prompt_aborted_tokens.discard(token)
        log(f"[prompt] starting token={token} length={len(prompt)} chars")

        thread = threading.Thread(
            target=self._run_prompt_request,
            args=(prompt, api_key, token, abort_event),
            daemon=True,
        )
        self.active_prompt_thread = thread
        thread.start()

    def abort_prompt(self) -> None:
        if not self.active_prompt_thread or not self.active_prompt_thread.is_alive():
            return
        if not self.current_prompt_abort_event or self.current_prompt_abort_event.is_set():
            return
        self.current_prompt_abort_event.set()
        if self.prompt_current_token is not None:
            self.prompt_aborted_tokens.add(self.prompt_current_token)
        if self.prompt_abort_button:
            self.prompt_abort_button.setEnabled(False)
        if self.prompt_send_button:
            self.prompt_send_button.setEnabled(True)
        if self.prompt_status:
            self.prompt_status.setText("Aborting...")
        self.show_info("Prompt abort requested.", duration=2)
        log(f"[prompt] abort requested for token={self.prompt_current_token}")
        self.active_prompt_thread = None
        self.current_prompt_abort_event = None

    # ----------------------------------------------------------- networking
    def _run_prompt_request(
        self,
        prompt: str,
        api_key: str,
        token: int,
        abort_event: threading.Event,
    ) -> None:
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": JSON_RESPONSE_INSTRUCTIONS},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            if abort_event.is_set():
                log(f"[prompt] token={token} abort detected before request dispatch")
                self._post_prompt_result(token, False, "Aborted")
                return
            log(f"[prompt] token={token} sending request to OpenAI")
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            raw_text = json.dumps(data, indent=2)
            if abort_event.is_set():
                log(f"[prompt] token={token} abort signaled after response")
                self._post_prompt_result(token, False, "Aborted")
                return
            log(f"[prompt] token={token} completed successfully")
            self._post_prompt_result(token, True, raw_text)
        except Exception as exc:
            log(f"[prompt] token={token} failed: {exc}")
            if not abort_event.is_set():
                self._post_prompt_result(token, False, str(exc))

    def _post_prompt_result(self, token: int, success: bool, text: str) -> None:
        QtCore.QMetaObject.invokeMethod(
            self,
            "_handle_prompt_result",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(int, int(token)),
            QtCore.Q_ARG(bool, bool(success)),
            QtCore.Q_ARG(str, str(text)),
        )

    @QtCore.Slot(int, bool, str)
    def _handle_prompt_result(self, token: int, success: bool, text: str) -> None:
        if token in self.prompt_aborted_tokens:
            self.prompt_aborted_tokens.discard(token)
            log(f"[prompt] ignoring aborted token={token}")
            return
        if token != self.prompt_current_token:
            log(f"[prompt] ignoring stale token={token}, current={self.prompt_current_token}")
            return
        self.active_prompt_thread = None
        self.current_prompt_abort_event = None
        if self.prompt_send_button:
            self.prompt_send_button.setEnabled(True)
        if self.prompt_abort_button:
            self.prompt_abort_button.setEnabled(False)
        if self.prompt_output:
            self.prompt_output.setPlainText(text)
        if self.prompt_status:
            self.prompt_status.setText("Completed" if success else "Failed")
        if success:
            self.show_info("Prompt completed.", duration=2)
            log(f"[prompt] token={token} finished successfully")
        else:
            self.show_info("Prompt failed.", duration=4)
            log(f"[prompt] token={token} failed; see output for details")
        self._update_structured_result(text)

    # ------------------------------------------------------ structured view
    def _update_structured_result(self, raw_text: str) -> None:
        if not self.prompt_structured_text:
            return
        self.prompt_last_structured = None
        if self.prompt_apply_button:
            self.prompt_apply_button.setEnabled(False)
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            self.prompt_structured_text.setPlainText(raw_text.strip())
            return

        if not isinstance(data, dict):
            self.prompt_structured_text.setPlainText(json.dumps(data, indent=2))
            return

        self.prompt_last_structured = data
        lines = []
        steps = data.get("steps") or []
        files = data.get("files") or []
        notes = data.get("notes")
        if steps:
            lines.append("Steps:")
            for idx, step in enumerate(steps, start=1):
                lines.append(f"  {idx}. {step}")
        if files:
            lines.append("\nFiles:")
            for entry in files:
                path = entry.get("path", "<unknown>")
                op = entry.get("operation", "update")
                lang = entry.get("language", "")
                lang_text = f" [{lang}]" if lang else ""
                content = entry.get("content")
                preview = (content or "").splitlines()
                preview_text = ""
                if preview:
                    preview_text = f"\n    > {preview[0][:80]}"
                    if len(preview) > 1:
                        preview_text += " ..."
                lines.append(f"  - {op.upper()} {path}{lang_text}{preview_text}")
        if notes:
            lines.append("\nNotes:")
            lines.append(f"  {notes}")
        elif not steps and not files:
            lines.append("Plain Response:")
            lines.append(raw_text.strip())

        self.prompt_structured_text.setPlainText("\n".join(lines).strip())
        if files:
            self._populate_files_table(files)
            if self.prompt_apply_button:
                self.prompt_apply_button.setEnabled(True)
        else:
            self._clear_files_table()

    def apply_structured_changes(self) -> None:
        if not self.prompt_last_structured:
            self.show_info("No structured response to apply.", duration=3)
            return
        files = self.prompt_last_structured.get("files") or []
        if not files:
            self.show_info("Structured response contains no file changes.", duration=3)
            return
        successes = 0
        failures = []
        for entry in files:
            path_value = entry.get("path")
            operation = (entry.get("operation") or "update").lower()
            content = entry.get("content") or ""
            if not path_value:
                failures.append("Missing path in one entry.")
                continue
            target = self._resolve_target_path(path_value)
            try:
                if operation in ("create", "update"):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with open(target, "w", encoding="utf-8", errors="ignore") as handle:
                        handle.write(content)
                    successes += 1
                elif operation == "delete":
                    if target.exists():
                        target.unlink()
                    successes += 1
                else:
                    failures.append(f"Unsupported operation '{operation}' for {path_value}")
            except Exception as exc:
                failures.append(f"{path_value}: {exc}")
                log(f"[prompt-apply] failed for {path_value}: {exc}")

        msg = f"Applied {successes} file operations."
        if failures:
            msg += f" Failures: {len(failures)}"
        self.show_info(msg, duration=4)
        if self.prompt_structured_text and failures:
            self.prompt_structured_text.appendPlainText("\nErrors:\n- " + "\n- ".join(failures))

    # ------------------------------------------------------------- helpers
    def _detect_repo_root(self) -> Path:
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / ".git").exists():
                return parent
        return Path.cwd()

    def _resolve_target_path(self, path_value: str) -> Path:
        path = Path(path_value)
        if path.is_absolute():
            return path
        return (self.repo_root / path).resolve()

    def _compose_prompt_with_context(self, prompt: str) -> str:
        sections = [prompt]
        ascii_widget = getattr(self, "ascii_view", None)
        ascii_text = ""
        if ascii_widget is not None:
            ascii_text = ascii_widget.toPlainText().strip()
        if ascii_text:
            sections.append("--- Project Tree Overview ---\n" + ascii_text)

        preview_widget = getattr(self, "preview_view", None)
        preview_text = ""
        if preview_widget is not None:
            preview_text = preview_widget.toPlainText().strip()
        if preview_text:
            sections.append("--- Preview Output ---\n" + preview_text)

        return "\n\n".join(section for section in sections if section)

    def _populate_files_table(self, files: list[dict]) -> None:
        table = getattr(self, "files_table", None)
        if not table:
            return
        table.setRowCount(0)
        for entry in files:
            row = table.rowCount()
            table.insertRow(row)
            path = entry.get("path", "<unknown>")
            op = entry.get("operation", "update")
            content = entry.get("content") or ""
            preview = content.splitlines()
            preview_text = preview[0][:160] + ("..." if len(preview) > 1 else "") if preview else ""
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(path))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(op.upper()))
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(preview_text))
        table.resizeColumnsToContents()

    def _clear_files_table(self) -> None:
        table = getattr(self, "files_table", None)
        if table:
            table.setRowCount(0)
