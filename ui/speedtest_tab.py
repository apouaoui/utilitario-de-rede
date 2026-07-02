import logging
from datetime import datetime

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.public_ip_tool import get_public_ip
from core.speedtest_history import add_result, clear_history, load_history
from core.speedtest_tool import run_speedtest
from ui.speed_gauge import SpeedGauge

logger = logging.getLogger(__name__)


class SpeedTestWorker(QThread):
    status = Signal(str)
    finished_test = Signal(dict)
    failed = Signal(str)

    def run(self):
        try:
            result = run_speedtest(progress_callback=self.status.emit)
            self.finished_test.emit(result)
        except Exception as exc:
            logger.exception("Falha no teste de velocidade")
            self.failed.emit(str(exc))


class PublicIpWorker(QThread):
    result_ready = Signal(str)

    def run(self):
        try:
            self.result_ready.emit(get_public_ip())
        except Exception:
            logger.exception("Falha ao obter IP publico")
            self.result_ready.emit("")


class SpeedTestTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._public_ip_worker = None
        self._last_result = None

        self.start_button = QPushButton("Iniciar Teste")
        self.start_button.clicked.connect(self._start)

        self.copy_button = QPushButton("Copiar Resultado")
        self.copy_button.clicked.connect(self._copy_result)
        self.copy_button.setEnabled(False)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setTextVisible(False)

        self.status_label = QLabel("Pronto.")

        self.download_gauge = SpeedGauge("Download")
        self.upload_gauge = SpeedGauge("Upload")

        self.ping_label = QLabel("--")
        self.server_label = QLabel("--")
        self.isp_label = QLabel("--")
        self.public_ip_label = QLabel("--")

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.start_button)
        top_layout.addWidget(self.copy_button)

        gauges_layout = QHBoxLayout()
        gauges_layout.addWidget(self.download_gauge)
        gauges_layout.addWidget(self.upload_gauge)

        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel("Ping:"))
        info_layout.addWidget(self.ping_label)
        info_layout.addWidget(QLabel("Servidor:"))
        info_layout.addWidget(self.server_label)
        info_layout.addWidget(QLabel("Provedor:"))
        info_layout.addWidget(self.isp_label)
        info_layout.addWidget(QLabel("IP Público:"))
        info_layout.addWidget(self.public_ip_label)
        info_layout.addStretch()

        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(
            ["Data/Hora", "Download", "Upload", "Ping", "Servidor"]
        )
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.clear_history_button = QPushButton("Limpar Histórico")
        self.clear_history_button.clicked.connect(self._clear_history)

        history_group = QGroupBox("Histórico")
        history_layout = QVBoxLayout(history_group)
        history_layout.addWidget(self.history_table)
        history_layout.addWidget(self.clear_history_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addLayout(gauges_layout)
        layout.addLayout(info_layout)
        layout.addWidget(history_group)

        self._load_history()
        self._fetch_public_ip()

    def _fetch_public_ip(self):
        self._public_ip_worker = PublicIpWorker()
        self._public_ip_worker.result_ready.connect(self._on_public_ip_ready)
        self._public_ip_worker.start()

    def _on_public_ip_ready(self, ip):
        self.public_ip_label.setText(ip if ip else "--")

    def _start(self):
        self.start_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.status_label.setText("Iniciando...")
        self.download_gauge.reset()
        self.upload_gauge.reset()
        self.progress_bar.setRange(0, 0)
        self._worker = SpeedTestWorker()
        self._worker.status.connect(self._on_status)
        self._worker.finished_test.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_status(self, message):
        self.status_label.setText(message)

    def _on_finished(self, result):
        self._last_result = result
        self._fetch_public_ip()
        self.download_gauge.set_value(result["download_mbps"])
        self.upload_gauge.set_value(result["upload_mbps"])
        self.ping_label.setText(f"{result['ping_ms']:.1f} ms")
        self.server_label.setText(result["server"])
        self.isp_label.setText(result["isp"])
        self.status_label.setText("Concluído.")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.start_button.setEnabled(True)
        self.copy_button.setEnabled(True)

        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "download_mbps": result["download_mbps"],
            "upload_mbps": result["upload_mbps"],
            "ping_ms": result["ping_ms"],
            "server": result["server"],
        }
        add_result(entry)
        self._add_history_row(entry, at_top=True)

    def _on_failed(self, message):
        self.status_label.setText(f"Erro: {message}")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(True)

    def _copy_result(self):
        if not self._last_result:
            return
        result = self._last_result
        text = (
            f"Download: {result['download_mbps']:.2f} Mbps\n"
            f"Upload: {result['upload_mbps']:.2f} Mbps\n"
            f"Ping: {result['ping_ms']:.1f} ms\n"
            f"Servidor: {result['server']}\n"
            f"Provedor: {result['isp']}\n"
            f"IP Público: {self.public_ip_label.text()}"
        )
        QGuiApplication.clipboard().setText(text)

    def _load_history(self):
        for entry in reversed(load_history()):
            self._add_history_row(entry, at_top=False)

    def _clear_history(self):
        if self.history_table.rowCount() == 0:
            return
        confirm = QMessageBox.question(
            self, "Limpar histórico", "Isso vai apagar todo o histórico de testes. Continuar?"
        )
        if confirm != QMessageBox.Yes:
            return
        clear_history()
        self.history_table.setRowCount(0)

    def _add_history_row(self, entry, at_top: bool):
        row = 0 if at_top else self.history_table.rowCount()
        self.history_table.insertRow(row)
        self.history_table.setItem(row, 0, QTableWidgetItem(entry["timestamp"]))
        self.history_table.setItem(row, 1, QTableWidgetItem(f"{entry['download_mbps']:.2f} Mbps"))
        self.history_table.setItem(row, 2, QTableWidgetItem(f"{entry['upload_mbps']:.2f} Mbps"))
        self.history_table.setItem(row, 3, QTableWidgetItem(f"{entry['ping_ms']:.1f} ms"))
        self.history_table.setItem(row, 4, QTableWidgetItem(entry["server"]))
