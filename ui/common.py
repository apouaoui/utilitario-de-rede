import subprocess

from PySide6.QtCore import QThread, Signal

from core.console_utils import get_console_encoding


class StreamProcessWorker(QThread):
    line_received = Signal(str)
    finished_run = Signal()

    def __init__(self, command: list[str]):
        super().__init__()
        self._command = command
        self._process = None

    def run(self):
        self._process = subprocess.Popen(
            self._command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding=get_console_encoding(),
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in self._process.stdout:
            self.line_received.emit(line.rstrip())
        self._process.wait()
        self.finished_run.emit()

    def stop(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
