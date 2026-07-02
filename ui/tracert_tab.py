from PySide6.QtGui import QColor, QFont, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.tracert_tool import build_tracert_command, is_timeout_line
from ui.common import StreamProcessWorker

_TIMEOUT_COLOR = QColor("#e57373")


class TracertTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("Endereço ou IP (ex: google.com)")
        self.host_input.returnPressed.connect(self._start)

        self.resolve_check = QCheckBox("Resolver nomes")

        self.start_button = QPushButton("Iniciar")
        self.start_button.clicked.connect(self._start)

        self.stop_button = QPushButton("Parar")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop)

        self.copy_button = QPushButton("Copiar resultado")
        self.copy_button.clicked.connect(self._copy_result)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 9))

        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Host:"))
        form_layout.addWidget(self.host_input)
        form_layout.addWidget(self.resolve_check)
        form_layout.addWidget(self.start_button)
        form_layout.addWidget(self.stop_button)
        form_layout.addWidget(self.copy_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.output)

    def _start(self):
        host = self.host_input.text().strip()
        if not host:
            return
        self.output.clear()
        command = build_tracert_command(host, self.resolve_check.isChecked())
        self._worker = StreamProcessWorker(command)
        self._worker.line_received.connect(self._on_line)
        self._worker.finished_run.connect(self._on_finished)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._worker.start()

    def _stop(self):
        if self._worker:
            self._worker.stop()

    def _copy_result(self):
        QGuiApplication.clipboard().setText(self.output.toPlainText())

    def _on_line(self, line):
        color = _TIMEOUT_COLOR if is_timeout_line(line) else None
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        if color:
            fmt.setForeground(color)
        cursor.insertText(line + "\n", fmt)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _on_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
