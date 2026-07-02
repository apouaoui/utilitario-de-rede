from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.ping_tool import build_ping_command, parse_ping_line
from ui.common import StreamProcessWorker
from ui.latency_graph import LatencyGraph

_REPLY_COLOR = QColor("#4caf50")
_LOST_COLOR = QColor("#e57373")


class PingTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._times_ms = []
        self._received = 0
        self._lost = 0

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("Endereço ou IP (ex: 8.8.8.8)")
        self.host_input.returnPressed.connect(self._start)

        self.count_input = QSpinBox()
        self.count_input.setRange(1, 100)
        self.count_input.setValue(4)

        self.continuous_check = QCheckBox("Contínuo (-t)")
        self.continuous_check.toggled.connect(
            lambda checked: self.count_input.setDisabled(checked)
        )

        self.start_button = QPushButton("Iniciar")
        self.start_button.clicked.connect(self._start)

        self.stop_button = QPushButton("Parar")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop)

        self.avg_label = QLabel("--")
        self.min_label = QLabel("--")
        self.max_label = QLabel("--")
        self.received_label = QLabel("0")
        self.lost_label = QLabel("0 (0%)")

        self.clear_button = QPushButton("Limpar")
        self.clear_button.clicked.connect(self._clear_log)

        self.graph = LatencyGraph()

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 9))

        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Host:"))
        form_layout.addWidget(self.host_input)
        form_layout.addWidget(QLabel("Qtd:"))
        form_layout.addWidget(self.count_input)
        form_layout.addWidget(self.continuous_check)
        form_layout.addWidget(self.start_button)
        form_layout.addWidget(self.stop_button)

        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("Média:"))
        stats_layout.addWidget(self.avg_label)
        stats_layout.addWidget(QLabel("Mín:"))
        stats_layout.addWidget(self.min_label)
        stats_layout.addWidget(QLabel("Máx:"))
        stats_layout.addWidget(self.max_label)
        stats_layout.addWidget(QLabel("Recebidos:"))
        stats_layout.addWidget(self.received_label)
        stats_layout.addWidget(QLabel("Perdidos:"))
        stats_layout.addWidget(self.lost_label)
        stats_layout.addStretch()
        stats_layout.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addLayout(stats_layout)
        layout.addWidget(self.graph)
        layout.addWidget(self.output)

    def set_host(self, host: str):
        self.host_input.setText(host)
        self.host_input.setFocus()

    def _start(self):
        host = self.host_input.text().strip()
        if not host:
            return
        self.output.clear()
        self.graph.clear()
        self._times_ms = []
        self._received = 0
        self._lost = 0
        self._update_stats()
        command = build_ping_command(
            host, self.count_input.value(), self.continuous_check.isChecked()
        )
        self._worker = StreamProcessWorker(command)
        self._worker.line_received.connect(self._on_line)
        self._worker.finished_run.connect(self._on_finished)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._worker.start()

    def _stop(self):
        if self._worker:
            self._worker.stop()

    def _clear_log(self):
        self.output.clear()

    def _on_line(self, line):
        result = parse_ping_line(line)
        if result is None:
            self._append_line(line)
            return
        if result["received"]:
            self._received += 1
            self._times_ms.append(result["time_ms"])
            self.graph.add_value(result["time_ms"])
            self._append_line(line, _REPLY_COLOR)
        else:
            self._lost += 1
            self._append_line(line, _LOST_COLOR)
        self._update_stats()

    def _append_line(self, line, color=None):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        if color:
            fmt.setForeground(color)
        cursor.insertText(line + "\n", fmt)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _update_stats(self):
        if self._times_ms:
            avg = sum(self._times_ms) / len(self._times_ms)
            self.avg_label.setText(f"{avg:.0f} ms")
            self.min_label.setText(f"{min(self._times_ms)} ms")
            self.max_label.setText(f"{max(self._times_ms)} ms")
        else:
            self.avg_label.setText("--")
            self.min_label.setText("--")
            self.max_label.setText("--")
        total = self._received + self._lost
        loss_pct = (self._lost / total * 100) if total else 0
        self.received_label.setText(str(self._received))
        self.lost_label.setText(f"{self._lost} ({loss_pct:.0f}%)")

    def _on_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
