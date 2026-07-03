import logging

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.admin_utils import is_admin, relaunch_as_admin
from core.anydesk_tool import clear_anydesk_data

logger = logging.getLogger(__name__)


class ActionWorker(QThread):
    finished_action = Signal(object)
    failed = Signal(str)

    def __init__(self, func, *args):
        super().__init__()
        self._func = func
        self._args = args

    def run(self):
        try:
            result = self._func(*self._args)
            self.finished_action.emit(result)
        except Exception as exc:
            logger.exception("Falha ao executar utilitario (%s)", self._func.__name__)
            self.failed.emit(str(exc))


class UtilitiesTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None

        self.admin_label = QLabel()
        self.admin_button = QPushButton("Reiniciar como Administrador")
        self.admin_button.clicked.connect(relaunch_as_admin)
        self._update_admin_status()

        self.clear_anydesk_button = QPushButton("Limpar Dados do AnyDesk")
        self.clear_anydesk_button.clicked.connect(self._clear_anydesk)

        self.status_label = QLabel("")

        admin_layout = QHBoxLayout()
        admin_layout.addWidget(self.admin_label)
        admin_layout.addWidget(self.admin_button)

        anydesk_group = QGroupBox("AnyDesk")
        anydesk_layout = QVBoxLayout(anydesk_group)
        anydesk_layout.addWidget(QLabel(
            "Fecha o AnyDesk (e o serviço, se houver), apaga as configurações salvas "
            "(incluindo dados do serviço em ProgramData, quando administrador) e "
            "instaladores .msi perdidos, gerando um novo ID na próxima vez que abrir."
        ))
        anydesk_layout.addWidget(self.clear_anydesk_button)

        layout = QVBoxLayout(self)
        layout.addLayout(admin_layout)
        layout.addWidget(anydesk_group)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _update_admin_status(self):
        if is_admin():
            self.admin_label.setText("Executando como Administrador ✔")
            self.admin_button.setVisible(False)
        else:
            self.admin_label.setText(
                "⚠ Não está como Administrador — dados do serviço do AnyDesk em "
                "ProgramData não serão removidos"
            )
            self.admin_button.setVisible(True)

    def _clear_anydesk(self):
        confirm = QMessageBox.question(
            self,
            "Limpar dados do AnyDesk",
            "Isso vai fechar o AnyDesk (se estiver aberto) e apagar as configurações "
            "salvas, gerando um novo ID na próxima vez que abrir. Deseja continuar?",
        )
        if confirm != QMessageBox.Yes:
            return

        self.clear_anydesk_button.setEnabled(False)
        self.status_label.setText("Limpando...")
        self._worker = ActionWorker(clear_anydesk_data)
        self._worker.finished_action.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished(self, cleared_paths):
        self.clear_anydesk_button.setEnabled(True)
        if cleared_paths:
            self.status_label.setText("Dados removidos: " + ", ".join(cleared_paths))
        else:
            self.status_label.setText("Nenhum dado do AnyDesk encontrado para remover.")

    def _on_failed(self, message):
        self.clear_anydesk_button.setEnabled(True)
        self.status_label.setText(f"Erro: {message}")
