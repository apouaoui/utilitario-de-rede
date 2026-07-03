import logging
from datetime import datetime

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
)

from core.updater import check_for_update, download_update, prepare_update_script
from core.version import VERSION
from ui.ipconfig_tab import IpConfigTab
from ui.network_drive_tab import NetworkDriveTab
from ui.ping_tab import PingTab
from ui.scanner_tab import ScannerTab
from ui.speedtest_tab import SpeedTestTab
from ui.tracert_tab import TracertTab
from ui.utilities_tab import UtilitiesTab

logger = logging.getLogger(__name__)


class UpdateCheckWorker(QThread):
    update_found = Signal(dict)

    def run(self):
        try:
            result = check_for_update()
            if result:
                self.update_found.emit(result)
        except Exception:
            logger.exception("Falha ao verificar atualizacoes")


class UpdateDownloadWorker(QThread):
    finished_download = Signal(str)
    failed = Signal(str)

    def __init__(self, url):
        super().__init__()
        self._url = url

    def run(self):
        try:
            new_path = download_update(self._url)
            self.finished_download.emit(new_path)
        except Exception as exc:
            logger.exception("Falha ao baixar atualizacao")
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Utilitário de Rede v{VERSION}")
        self.resize(900, 620)

        self._pending_update = None
        self._update_check_worker = None
        self._download_worker = None

        self.tabs = QTabWidget()
        ping_tab = PingTab()
        scanner_tab = ScannerTab()
        self.tabs.addTab(ping_tab, "Ping")
        self.tabs.addTab(TracertTab(), "Tracert")
        self.tabs.addTab(scanner_tab, "Scanner de Rede")
        self.tabs.addTab(SpeedTestTab(), "Speed Test")
        self.tabs.addTab(IpConfigTab(), "Configurar IP")
        self.tabs.addTab(NetworkDriveTab(), "Unidades de Rede")
        self.tabs.addTab(UtilitiesTab(), "Utilitários")
        self.setCentralWidget(self.tabs)

        scanner_tab.ping_requested.connect(lambda ip: self._send_to_ping(ping_tab, ip))

        self.update_button = QPushButton("Atualização disponível")
        self.update_button.setVisible(False)
        self.update_button.clicked.connect(self._start_update)
        self.statusBar().addPermanentWidget(self.update_button)

        year = datetime.now().year
        footer = QLabel(f"Feito por Arthur — © {year} Todos os direitos reservados — v{VERSION}")
        self.statusBar().addPermanentWidget(footer)

        self._update_check_worker = UpdateCheckWorker()
        self._update_check_worker.update_found.connect(self._on_update_found)
        self._update_check_worker.start()

    def _send_to_ping(self, ping_tab, ip):
        ping_tab.set_host(ip)
        self.tabs.setCurrentWidget(ping_tab)

    def _on_update_found(self, info):
        self._pending_update = info
        self.update_button.setText(f"Atualizar para v{info['version']}")
        self.update_button.setVisible(True)

    def _start_update(self):
        if not self._pending_update:
            return
        confirm = QMessageBox.question(
            self,
            "Atualizar",
            f"Baixar e instalar a versão {self._pending_update['version']}? "
            "O aplicativo vai fechar e reabrir automaticamente.",
        )
        if confirm != QMessageBox.Yes:
            return

        self.update_button.setEnabled(False)
        self.update_button.setText("Baixando atualização...")
        self._download_worker = UpdateDownloadWorker(self._pending_update["url"])
        self._download_worker.finished_download.connect(self._on_update_downloaded)
        self._download_worker.failed.connect(self._on_update_failed)
        self._download_worker.start()

    def _on_update_downloaded(self, new_path):
        prepare_update_script(new_path)
        QApplication.quit()

    def _on_update_failed(self, message):
        QMessageBox.warning(self, "Erro ao atualizar", message)
        self.update_button.setEnabled(True)
        self.update_button.setText(f"Atualizar para v{self._pending_update['version']}")
