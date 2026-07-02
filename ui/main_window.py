from datetime import datetime

from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget

from core.version import VERSION
from ui.ipconfig_tab import IpConfigTab
from ui.network_drive_tab import NetworkDriveTab
from ui.ping_tab import PingTab
from ui.scanner_tab import ScannerTab
from ui.speedtest_tab import SpeedTestTab
from ui.tracert_tab import TracertTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Utilitário de Rede v{VERSION}")
        self.resize(900, 620)

        self.tabs = QTabWidget()
        ping_tab = PingTab()
        scanner_tab = ScannerTab()
        self.tabs.addTab(ping_tab, "Ping")
        self.tabs.addTab(TracertTab(), "Tracert")
        self.tabs.addTab(scanner_tab, "Scanner de Rede")
        self.tabs.addTab(SpeedTestTab(), "Speed Test")
        self.tabs.addTab(IpConfigTab(), "Configurar IP")
        self.tabs.addTab(NetworkDriveTab(), "Unidades de Rede")
        self.setCentralWidget(self.tabs)

        scanner_tab.ping_requested.connect(lambda ip: self._send_to_ping(ping_tab, ip))

        year = datetime.now().year
        footer = QLabel(f"Feito por Arthur — © {year} Todos os direitos reservados — v{VERSION}")
        self.statusBar().addPermanentWidget(footer)

    def _send_to_ping(self, ping_tab, ip):
        ping_tab.set_host(ip)
        self.tabs.setCurrentWidget(ping_tab)
