import logging
import os

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.drive_profiles import add_profile, delete_profile, load_profiles
from core.network_drives_tool import (
    available_drive_letters,
    disconnect_drive,
    list_mapped_drives,
    map_drive,
    reconnect_drive,
)

logger = logging.getLogger(__name__)


class DriveActionWorker(QThread):
    finished_action = Signal()
    failed = Signal(str)

    def __init__(self, func, *args):
        super().__init__()
        self._func = func
        self._args = args

    def run(self):
        try:
            self._func(*self._args)
            self.finished_action.emit()
        except Exception as exc:
            logger.exception("Falha ao executar acao de unidade de rede (%s)", self._func.__name__)
            self.failed.emit(str(exc))


class NetworkDriveTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Letra", "Caminho", "Status", "Espaço"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(lambda row, _col: self._open_in_explorer(row))

        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self._refresh_drives)

        self.disconnect_button = QPushButton("Desconectar Selecionada")
        self.disconnect_button.clicked.connect(self._disconnect_selected)

        self.profile_combo = QComboBox()
        self.profile_combo.activated.connect(self._on_profile_selected)
        self.save_profile_button = QPushButton("Salvar perfil atual")
        self.save_profile_button.clicked.connect(self._save_profile)
        self.delete_profile_button = QPushButton("Excluir")
        self.delete_profile_button.clicked.connect(self._delete_profile)

        self.letter_combo = QComboBox()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText(r"\\servidor\pasta")
        self.path_input.returnPressed.connect(self._map_drive)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("(opcional)")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("(opcional)")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.persist_check = QCheckBox("Reconectar ao iniciar o Windows")
        self.persist_check.setChecked(True)

        self.map_button = QPushButton("Mapear Unidade")
        self.map_button.clicked.connect(self._map_drive)

        self.status_label = QLabel("")

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.refresh_button)
        top_layout.addWidget(self.disconnect_button)
        top_layout.addStretch()

        profiles_group = QGroupBox("Perfis salvos")
        profiles_layout = QHBoxLayout(profiles_group)
        profiles_layout.addWidget(self.profile_combo, 1)
        profiles_layout.addWidget(self.save_profile_button)
        profiles_layout.addWidget(self.delete_profile_button)

        map_group = QGroupBox("Mapear nova unidade")
        form = QFormLayout(map_group)
        form.addRow("Letra:", self.letter_combo)
        form.addRow("Caminho:", self.path_input)
        form.addRow("Usuário:", self.username_input)
        form.addRow("Senha:", self.password_input)
        form.addRow(self.persist_check)
        form.addRow(self.map_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.table)
        layout.addWidget(profiles_group)
        layout.addWidget(map_group)
        layout.addWidget(self.status_label)

        self._refresh_drives()
        self._refresh_profiles()

    def _refresh_drives(self):
        try:
            drives = list_mapped_drives()
            letters = available_drive_letters()
        except Exception as exc:
            self.status_label.setText(f"Erro: {exc}")
            return

        self.table.setRowCount(len(drives))
        for row, drive in enumerate(drives):
            self.table.setItem(row, 0, QTableWidgetItem(drive["letter"]))
            self.table.setItem(row, 1, QTableWidgetItem(drive["path"]))
            self.table.setItem(row, 2, QTableWidgetItem(drive["status"]))
            self.table.setItem(row, 3, QTableWidgetItem(drive["space"]))

        self.letter_combo.clear()
        self.letter_combo.addItems(letters)

    def _disconnect_selected(self):
        row = self.table.currentRow()
        if row < 0:
            self.status_label.setText("Selecione uma unidade na lista.")
            return
        self._disconnect_row(row)

    def _disconnect_row(self, row):
        letter = self.table.item(row, 0).text()
        confirm = QMessageBox.question(
            self, "Desconectar unidade", f'Desconectar a unidade "{letter}"?'
        )
        if confirm != QMessageBox.Yes:
            return

        self.disconnect_button.setEnabled(False)
        self.status_label.setText("Desconectando...")
        self._worker = DriveActionWorker(disconnect_drive, letter.rstrip(":"))
        self._worker.finished_action.connect(self._on_action_finished)
        self._worker.failed.connect(self._on_action_failed)
        self._worker.start()

    def _reconnect_row(self, row):
        letter = self.table.item(row, 0).text().rstrip(":")
        path = self.table.item(row, 1).text()
        self.status_label.setText("Reconectando...")
        self._worker = DriveActionWorker(reconnect_drive, letter, path)
        self._worker.finished_action.connect(self._on_action_finished)
        self._worker.failed.connect(self._on_action_failed)
        self._worker.start()

    def _open_in_explorer(self, row):
        letter = self.table.item(row, 0).text().rstrip(":")
        if not letter:
            return
        os.startfile(f"{letter}:\\")

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        copy_action = menu.addAction("Copiar Caminho")
        open_action = menu.addAction("Abrir no Explorer")
        reconnect_action = menu.addAction("Reconectar")
        disconnect_action = menu.addAction("Desconectar")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == copy_action:
            QGuiApplication.clipboard().setText(self.table.item(row, 1).text())
        elif action == open_action:
            self._open_in_explorer(row)
        elif action == reconnect_action:
            self._reconnect_row(row)
        elif action == disconnect_action:
            self._disconnect_row(row)

    def _map_drive(self):
        letter = self.letter_combo.currentText().rstrip(":")
        path = self.path_input.text().strip()
        if not letter or not path:
            self.status_label.setText("Informe a letra e o caminho da unidade.")
            return

        self.map_button.setEnabled(False)
        self.status_label.setText("Mapeando...")
        self._worker = DriveActionWorker(
            map_drive,
            letter,
            path,
            self.username_input.text().strip(),
            self.password_input.text(),
            self.persist_check.isChecked(),
        )
        self._worker.finished_action.connect(self._on_action_finished)
        self._worker.failed.connect(self._on_action_failed)
        self._worker.start()

    def _on_action_finished(self):
        self.status_label.setText("Concluído.")
        self.disconnect_button.setEnabled(True)
        self.map_button.setEnabled(True)
        self.path_input.clear()
        self.username_input.clear()
        self.password_input.clear()
        self._refresh_drives()

    def _on_action_failed(self, message):
        self.status_label.setText(f"Erro: {message}")
        self.disconnect_button.setEnabled(True)
        self.map_button.setEnabled(True)

    def _refresh_profiles(self):
        self.profile_combo.clear()
        self.profile_combo.addItem("", None)
        for profile in load_profiles():
            self.profile_combo.addItem(profile["name"], profile)

    def _on_profile_selected(self, _index):
        profile = self.profile_combo.currentData()
        if not profile:
            return
        self.path_input.setText(profile.get("path", ""))

    def _save_profile(self):
        path = self.path_input.text().strip()
        if not path:
            self.status_label.setText("Informe o caminho antes de salvar o perfil.")
            return
        name, ok = QInputDialog.getText(self, "Salvar perfil", "Nome do perfil:")
        name = name.strip()
        if not ok or not name:
            return
        add_profile({"name": name, "path": path})
        self._refresh_profiles()
        index = self.profile_combo.findText(name)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)

    def _delete_profile(self):
        profile = self.profile_combo.currentData()
        if not profile:
            return
        confirm = QMessageBox.question(
            self, "Excluir perfil", f'Excluir o perfil "{profile["name"]}"?'
        )
        if confirm != QMessageBox.Yes:
            return
        delete_profile(profile["name"])
        self._refresh_profiles()
