import csv
import logging
import threading

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.scanner_tool import get_local_networks, parse_targets, scan_network

logger = logging.getLogger(__name__)
_SELF_COLOR = QColor("#4fc3f7")


class ScannerWorker(QThread):
    progress = Signal(int, int)
    finished_scan = Signal(list)
    failed = Signal(str)

    def __init__(self, targets):
        super().__init__()
        self._targets = targets
        self._cancel_event = threading.Event()

    def run(self):
        try:
            results = scan_network(
                self._targets,
                progress_callback=lambda done, total: self.progress.emit(done, total),
                cancel_event=self._cancel_event,
            )
            self.finished_scan.emit(results)
        except Exception as exc:
            logger.exception("Falha ao escanear a rede")
            self.failed.emit(str(exc))

    def stop(self):
        self._cancel_event.set()


class ScannerTab(QWidget):
    ping_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self._worker = None
        self._local_ip = None

        self.network_combo = QComboBox()
        self.network_combo.currentIndexChanged.connect(self._on_network_combo_changed)

        self.refresh_button = QPushButton("Atualizar Interfaces")
        self.refresh_button.clicked.connect(self._refresh_networks)

        self.network_input = QLineEdit()
        self.network_input.setPlaceholderText(
            "Ex: 192.168.0.0/24 ou 192.168.0.10-192.168.0.20, 172.16.110.0/24"
        )
        self.network_input.returnPressed.connect(self._start_scan)

        self.scan_button = QPushButton("Escanear")
        self.scan_button.clicked.connect(self._start_scan)

        self.stop_button = QPushButton("Parar")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_scan)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filtrar por IP, MAC ou hostname...")
        self.filter_input.textChanged.connect(self._apply_filter)

        self.export_button = QPushButton("Exportar CSV")
        self.export_button.clicked.connect(self._export_csv)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["IP", "MAC", "Hostname"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 150)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        self.status_label = QLabel("")

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.network_combo, 1)
        top_layout.addWidget(self.refresh_button)

        network_layout = QHBoxLayout()
        network_layout.addWidget(QLabel("Rede:"))
        network_layout.addWidget(self.network_input, 1)
        network_layout.addWidget(self.scan_button)
        network_layout.addWidget(self.stop_button)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self.filter_input, 1)
        filter_layout.addWidget(self.export_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addLayout(network_layout)
        layout.addLayout(filter_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.table)
        layout.addWidget(self.status_label)

        self._refresh_networks()

    def _refresh_networks(self):
        self.network_combo.clear()
        networks = get_local_networks()
        for iface, ip, net in networks:
            self.network_combo.addItem(f"{iface} — {net}", (ip, net))
        if not networks:
            self.status_label.setText(
                "Nenhuma interface detectada automaticamente. Digite a rede manualmente (ex: 192.168.0.0/24)."
            )

    def _on_network_combo_changed(self, _index):
        data = self.network_combo.currentData()
        if data is None:
            return
        local_ip, network = data
        self._local_ip = local_ip
        self.network_input.setText(str(network))

    def _start_scan(self):
        try:
            targets = parse_targets(self.network_input.text())
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        if len(targets) > 1024:
            self.status_label.setText("Faixa muito grande para varrer (máximo 1024 endereços).")
            return

        self.filter_input.clear()
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.scan_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Escaneando...")
        self._worker = ScannerWorker(targets)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_scan.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _stop_scan(self):
        if self._worker:
            self._worker.stop()
        self.stop_button.setEnabled(False)

    def _on_progress(self, done, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)

    def _on_finished(self, results):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(results))
        for row, item in enumerate(results):
            is_self = item["ip"] == self._local_ip
            for col, value in enumerate([item["ip"], item["mac"], item["hostname"]]):
                cell = QTableWidgetItem(value)
                if is_self:
                    font = cell.font()
                    font.setBold(True)
                    cell.setFont(font)
                    cell.setForeground(QBrush(_SELF_COLOR))
                self.table.setItem(row, col, cell)
        self.table.setSortingEnabled(True)
        self.status_label.setText(f"{len(results)} dispositivo(s) encontrado(s).")
        self.scan_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _on_failed(self, message):
        self.status_label.setText(f"Erro: {message}")
        self.scan_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _apply_filter(self, text):
        text = text.strip().lower()
        for row in range(self.table.rowCount()):
            if not text:
                self.table.setRowHidden(row, False)
                continue
            match = any(
                text in (self.table.item(row, col).text().lower() if self.table.item(row, col) else "")
                for col in range(self.table.columnCount())
            )
            self.table.setRowHidden(row, not match)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "scan_rede.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["IP", "MAC", "Hostname"])
            for row in range(self.table.rowCount()):
                if self.table.isRowHidden(row):
                    continue
                writer.writerow([
                    self.table.item(row, col).text() if self.table.item(row, col) else ""
                    for col in range(self.table.columnCount())
                ])
        self.status_label.setText(f"Exportado para {path}")

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        ip = self.table.item(row, 0).text()
        menu = QMenu(self)
        copy_action = menu.addAction("Copiar IP")
        ping_action = menu.addAction("Enviar para Ping")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == copy_action:
            QGuiApplication.clipboard().setText(ip)
        elif action == ping_action:
            self.ping_requested.emit(ip)
