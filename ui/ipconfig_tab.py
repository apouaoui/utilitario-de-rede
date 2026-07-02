import ipaddress
import logging
import threading

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.admin_utils import is_admin, relaunch_as_admin
from core.ip_config_tool import (
    add_extra_ip,
    list_extra_ips,
    list_interfaces,
    normalize_netmask,
    remove_extra_ip,
    set_dhcp,
    set_static_ip,
    test_gateway,
    validate_static_config,
)
from core.ip_profiles import add_profile, delete_profile, load_profiles
from core.scanner_tool import find_free_ips, parse_targets

logger = logging.getLogger(__name__)


class IpConfigWorker(QThread):
    finished_apply = Signal()
    failed = Signal(str)

    def __init__(self, func, *args):
        super().__init__()
        self._func = func
        self._args = args

    def run(self):
        try:
            self._func(*self._args)
            self.finished_apply.emit()
        except Exception as exc:
            logger.exception("Falha ao executar acao de configuracao de IP (%s)", self._func.__name__)
            self.failed.emit(str(exc))


class GatewayTestWorker(QThread):
    result_ready = Signal(bool)

    def __init__(self, gateway):
        super().__init__()
        self._gateway = gateway

    def run(self):
        self.result_ready.emit(test_gateway(self._gateway))


class FreeIpWorker(QThread):
    progress = Signal(int, int)
    finished_scan = Signal(list)
    failed = Signal(str)

    def __init__(self, targets):
        super().__init__()
        self._targets = targets
        self._cancel_event = threading.Event()

    def run(self):
        try:
            free_ips = find_free_ips(
                self._targets,
                progress_callback=lambda done, total: self.progress.emit(done, total),
                cancel_event=self._cancel_event,
            )
            self.finished_scan.emit(free_ips)
        except Exception as exc:
            logger.exception("Falha na busca de IPs livres")
            self.failed.emit(str(exc))

    def stop(self):
        self._cancel_event.set()


class IpConfigTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._free_ip_worker = None
        self._gateway_worker = None
        self._extra_ip_worker = None
        self._pending_gateway_test = None
        self._interfaces = []

        self.admin_label = QLabel()
        self.admin_button = QPushButton("Reiniciar como Administrador")
        self.admin_button.clicked.connect(relaunch_as_admin)
        self._update_admin_status()

        self.interface_combo = QComboBox()
        self.interface_combo.currentIndexChanged.connect(self._on_interface_changed)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self._refresh_interfaces)

        self.link_status_label = QLabel("")

        self.dhcp_radio = QRadioButton("Obter IP automaticamente (DHCP)")
        self.static_radio = QRadioButton("Usar o seguinte IP")
        self.dhcp_radio.setChecked(True)
        self.dhcp_radio.toggled.connect(self._toggle_static_fields)

        self.ip_input = QLineEdit()
        self.mask_input = QLineEdit()
        self.mask_input.setText("255.255.255.0")
        self.mask_input.setPlaceholderText("255.255.255.0 ou /24")
        self.gateway_input = QLineEdit()
        self.dns_input = QLineEdit()

        self.apply_button = QPushButton("Aplicar")
        self.apply_button.clicked.connect(self._apply)

        self.status_label = QLabel("")

        self.network_input = QLineEdit()
        self.network_input.setPlaceholderText(
            "Ex: 192.168.0.0/24 ou 192.168.0.10-192.168.0.20, 172.16.110.0/24"
        )
        self.network_input.returnPressed.connect(self._start_free_scan)
        self.find_free_button = QPushButton("Buscar IPs livres")
        self.find_free_button.clicked.connect(self._start_free_scan)
        self.stop_free_scan_button = QPushButton("Parar")
        self.stop_free_scan_button.setEnabled(False)
        self.stop_free_scan_button.clicked.connect(self._stop_free_scan)
        self.free_scan_progress = QProgressBar()
        self.free_ips_list = QListWidget()
        self.free_ips_list.setMaximumHeight(120)
        self.free_ips_list.itemClicked.connect(self._on_free_ip_selected)

        self.extra_ips_list = QListWidget()
        self.extra_ips_list.setMaximumHeight(80)
        self.extra_ip_input = QLineEdit()
        self.extra_ip_input.setPlaceholderText("Novo IP (ex: 192.168.0.116)")
        self.extra_mask_input = QLineEdit()
        self.extra_mask_input.setText("255.255.255.0")
        self.extra_mask_input.setPlaceholderText("255.255.255.0 ou /24")
        self.add_extra_ip_button = QPushButton("Adicionar")
        self.add_extra_ip_button.clicked.connect(self._add_extra_ip)
        self.remove_extra_ip_button = QPushButton("Remover Selecionado")
        self.remove_extra_ip_button.clicked.connect(self._remove_extra_ip)

        self.profile_combo = QComboBox()
        self.profile_combo.activated.connect(self._on_profile_selected)
        self.save_profile_button = QPushButton("Salvar perfil atual")
        self.save_profile_button.clicked.connect(self._save_profile)
        self.delete_profile_button = QPushButton("Excluir")
        self.delete_profile_button.clicked.connect(self._delete_profile)

        admin_layout = QHBoxLayout()
        admin_layout.addWidget(self.admin_label)
        admin_layout.addWidget(self.admin_button)

        iface_layout = QHBoxLayout()
        iface_layout.addWidget(self.interface_combo, 1)
        iface_layout.addWidget(self.refresh_button)

        profiles_group = QGroupBox("Perfis salvos")
        profiles_layout = QHBoxLayout(profiles_group)
        profiles_layout.addWidget(self.profile_combo, 1)
        profiles_layout.addWidget(self.save_profile_button)
        profiles_layout.addWidget(self.delete_profile_button)

        free_ip_group = QGroupBox("Buscar IP livre na rede")
        free_ip_layout = QVBoxLayout(free_ip_group)
        network_layout = QHBoxLayout()
        network_layout.addWidget(QLabel("Rede:"))
        network_layout.addWidget(self.network_input, 1)
        network_layout.addWidget(self.find_free_button)
        network_layout.addWidget(self.stop_free_scan_button)
        free_ip_layout.addLayout(network_layout)
        free_ip_layout.addWidget(self.free_scan_progress)
        free_ip_layout.addWidget(self.free_ips_list)

        static_group = QGroupBox()
        form = QFormLayout(static_group)
        form.addRow("IP:", self.ip_input)
        form.addRow("Máscara:", self.mask_input)
        form.addRow("Gateway:", self.gateway_input)
        form.addRow("DNS:", self.dns_input)

        extra_ip_group = QGroupBox("IPs adicionais na interface")
        extra_ip_layout = QVBoxLayout(extra_ip_group)
        extra_ip_layout.addWidget(self.extra_ips_list)
        extra_ip_form_layout = QHBoxLayout()
        extra_ip_form_layout.addWidget(self.extra_ip_input, 1)
        extra_ip_form_layout.addWidget(self.extra_mask_input)
        extra_ip_form_layout.addWidget(self.add_extra_ip_button)
        extra_ip_layout.addLayout(extra_ip_form_layout)
        extra_ip_layout.addWidget(self.remove_extra_ip_button)

        layout = QVBoxLayout(self)
        layout.addLayout(admin_layout)
        layout.addLayout(iface_layout)
        layout.addWidget(self.link_status_label)
        layout.addWidget(profiles_group)
        layout.addWidget(free_ip_group)
        layout.addWidget(self.dhcp_radio)
        layout.addWidget(self.static_radio)
        layout.addWidget(static_group)
        layout.addWidget(extra_ip_group)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.status_label)
        layout.addStretch()

        self._refresh_interfaces()
        self._refresh_profiles()
        self._toggle_static_fields()

    def _update_admin_status(self):
        if is_admin():
            self.admin_label.setText("Executando como Administrador ✔")
            self.admin_button.setVisible(False)
        else:
            self.admin_label.setText(
                "⚠ Não está como Administrador — necessário para aplicar mudanças de IP"
            )
            self.admin_button.setVisible(True)

    def _refresh_interfaces(self):
        self.interface_combo.clear()
        self._interfaces = list_interfaces()
        for iface in self._interfaces:
            label = f"{iface['name']} — {iface['ip']}"
            self.interface_combo.addItem(label, iface)

    def _on_interface_changed(self, _index):
        iface = self.interface_combo.currentData()
        if not iface:
            return
        try:
            network = ipaddress.ip_network(f"{iface['ip']}/{iface['netmask']}", strict=False)
            self.network_input.setText(str(network))
        except ValueError:
            self.network_input.clear()

        self.ip_input.setText(iface["ip"])
        self.mask_input.setText(iface["netmask"])
        self.gateway_input.setText(iface.get("gateway", ""))
        self.dns_input.setText(iface.get("dns", ""))
        if iface["dhcp"]:
            self.dhcp_radio.setChecked(True)
        else:
            self.static_radio.setChecked(True)

        if iface["is_up"]:
            self.link_status_label.setText("")
        else:
            self.link_status_label.setText(
                "⚠ Interface sem conexão (cabo desconectado ou sem sinal)"
            )

        self._refresh_extra_ips()

    def _refresh_extra_ips(self):
        iface = self.interface_combo.currentData()
        self.extra_ips_list.clear()
        if not iface:
            return
        try:
            self.extra_ips_list.addItems(list_extra_ips(iface["name"], primary_ip=iface["ip"]))
        except Exception as exc:
            self.status_label.setText(f"Erro ao listar IPs adicionais: {exc}")

    def _add_extra_ip(self):
        iface = self.interface_combo.currentData()
        if not iface:
            return
        if not is_admin():
            self.status_label.setText("Erro: execute como Administrador para aplicar mudanças.")
            return

        ip = self.extra_ip_input.text().strip()
        netmask = normalize_netmask(self.extra_mask_input.text())
        error = validate_static_config(ip, netmask)
        if error:
            self.status_label.setText(error)
            return

        self.add_extra_ip_button.setEnabled(False)
        self.status_label.setText("Adicionando IP...")
        self._extra_ip_worker = IpConfigWorker(add_extra_ip, iface["name"], ip, netmask)
        self._extra_ip_worker.finished_apply.connect(self._on_extra_ip_finished)
        self._extra_ip_worker.failed.connect(self._on_extra_ip_failed)
        self._extra_ip_worker.start()

    def _remove_extra_ip(self):
        iface = self.interface_combo.currentData()
        if not iface:
            return
        item = self.extra_ips_list.currentItem()
        if not item:
            self.status_label.setText("Selecione um IP adicional na lista.")
            return
        if not is_admin():
            self.status_label.setText("Erro: execute como Administrador para aplicar mudanças.")
            return

        confirm = QMessageBox.question(self, "Remover IP", f'Remover o IP "{item.text()}"?')
        if confirm != QMessageBox.Yes:
            return

        self.remove_extra_ip_button.setEnabled(False)
        self.status_label.setText("Removendo IP...")
        self._extra_ip_worker = IpConfigWorker(remove_extra_ip, iface["name"], item.text())
        self._extra_ip_worker.finished_apply.connect(self._on_extra_ip_finished)
        self._extra_ip_worker.failed.connect(self._on_extra_ip_failed)
        self._extra_ip_worker.start()

    def _on_extra_ip_finished(self):
        self.status_label.setText("Concluído.")
        self.add_extra_ip_button.setEnabled(True)
        self.remove_extra_ip_button.setEnabled(True)
        self.extra_ip_input.clear()
        self._refresh_extra_ips()

    def _on_extra_ip_failed(self, message):
        self.status_label.setText(f"Erro: {message}")
        self.add_extra_ip_button.setEnabled(True)
        self.remove_extra_ip_button.setEnabled(True)

    def _start_free_scan(self):
        try:
            targets = parse_targets(self.network_input.text())
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        if len(targets) > 1024:
            self.status_label.setText("Faixa muito grande para varrer (máximo 1024 endereços).")
            return

        self.free_ips_list.clear()
        self.free_scan_progress.setValue(0)
        self.find_free_button.setEnabled(False)
        self.stop_free_scan_button.setEnabled(True)
        self.status_label.setText("Buscando IPs livres...")
        self._free_ip_worker = FreeIpWorker(targets)
        self._free_ip_worker.progress.connect(self._on_free_scan_progress)
        self._free_ip_worker.finished_scan.connect(self._on_free_scan_finished)
        self._free_ip_worker.failed.connect(self._on_free_scan_failed)
        self._free_ip_worker.start()

    def _stop_free_scan(self):
        if self._free_ip_worker:
            self._free_ip_worker.stop()
        self.stop_free_scan_button.setEnabled(False)

    def _on_free_scan_progress(self, done, total):
        self.free_scan_progress.setMaximum(total)
        self.free_scan_progress.setValue(done)

    def _on_free_scan_finished(self, free_ips):
        self.free_ips_list.addItems(free_ips)
        self.find_free_button.setEnabled(True)
        self.stop_free_scan_button.setEnabled(False)
        self.status_label.setText(f"{len(free_ips)} IP(s) livre(s) encontrado(s).")

    def _on_free_scan_failed(self, message):
        self.find_free_button.setEnabled(True)
        self.stop_free_scan_button.setEnabled(False)
        self.status_label.setText(f"Erro na busca: {message}")

    def _on_free_ip_selected(self, item):
        self.ip_input.setText(item.text())
        try:
            network = ipaddress.ip_network(self.network_input.text().strip(), strict=False)
            self.mask_input.setText(str(network.netmask))
        except ValueError:
            pass
        self.static_radio.setChecked(True)

    def _refresh_profiles(self):
        self.profile_combo.clear()
        self.profile_combo.addItem("", None)
        for profile in load_profiles():
            self.profile_combo.addItem(profile["name"], profile)

    def _on_profile_selected(self, _index):
        profile = self.profile_combo.currentData()
        if not profile:
            return
        self.ip_input.setText(profile.get("ip", ""))
        self.mask_input.setText(profile.get("netmask", ""))
        self.gateway_input.setText(profile.get("gateway", ""))
        self.dns_input.setText(profile.get("dns", ""))
        self.static_radio.setChecked(True)

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Salvar perfil", "Nome do perfil:")
        name = name.strip()
        if not ok or not name:
            return
        profile = {
            "name": name,
            "ip": self.ip_input.text().strip(),
            "netmask": self.mask_input.text().strip(),
            "gateway": self.gateway_input.text().strip(),
            "dns": self.dns_input.text().strip(),
        }
        add_profile(profile)
        self._refresh_profiles()
        index = self.profile_combo.findText(name)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)

    def _delete_profile(self):
        profile = self.profile_combo.currentData()
        if not profile:
            return
        confirm = QMessageBox.question(
            self, "Excluir perfil", f"Excluir o perfil \"{profile['name']}\"?"
        )
        if confirm != QMessageBox.Yes:
            return
        delete_profile(profile["name"])
        self._refresh_profiles()

    def _toggle_static_fields(self):
        enabled = self.static_radio.isChecked()
        self.ip_input.setEnabled(enabled)
        self.mask_input.setEnabled(enabled)
        self.gateway_input.setEnabled(enabled)
        self.dns_input.setEnabled(enabled)

    def _apply(self):
        iface = self.interface_combo.currentData()
        if not iface:
            return
        if not is_admin():
            self.status_label.setText("Erro: execute como Administrador para aplicar mudanças.")
            return

        self._pending_gateway_test = None

        if self.dhcp_radio.isChecked():
            worker_args = (set_dhcp, iface["name"])
        else:
            ip = self.ip_input.text().strip()
            netmask = normalize_netmask(self.mask_input.text())
            gateway = self.gateway_input.text().strip()
            dns = self.dns_input.text().strip()
            error = validate_static_config(ip, netmask, gateway, dns)
            if error:
                self.status_label.setText(error)
                return
            self.mask_input.setText(netmask)
            worker_args = (set_static_ip, iface["name"], ip, netmask, gateway, dns)
            self._pending_gateway_test = gateway or None

        confirm = QMessageBox.question(
            self,
            "Aplicar configuração",
            "Isso pode interromper sua conexão de rede atual. Deseja continuar?",
        )
        if confirm != QMessageBox.Yes:
            return

        self.apply_button.setEnabled(False)
        self.status_label.setText("Aplicando...")
        self._worker = IpConfigWorker(*worker_args)
        self._worker.finished_apply.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished(self):
        self.apply_button.setEnabled(True)
        self._refresh_interfaces()

        if self._pending_gateway_test:
            self.status_label.setText("Configuração aplicada. Testando gateway...")
            self._gateway_worker = GatewayTestWorker(self._pending_gateway_test)
            self._gateway_worker.result_ready.connect(self._on_gateway_test_result)
            self._gateway_worker.start()
        else:
            self.status_label.setText("Configuração aplicada com sucesso.")

    def _on_gateway_test_result(self, success: bool):
        if success:
            self.status_label.setText("Configuração aplicada. Gateway respondeu ao ping ✔")
        else:
            self.status_label.setText(
                "Configuração aplicada, mas o gateway não respondeu ao ping."
            )

    def _on_failed(self, message):
        self.status_label.setText(f"Erro: {message}")
        self.apply_button.setEnabled(True)
