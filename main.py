import logging
import os
import sys
import traceback

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from core.logging_setup import setup_logging
from core.resources import get_resource_path
from core.version import VERSION
from ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical("Erro nao tratado:\n%s", message)
    QMessageBox.critical(None, "Erro inesperado", message[-2000:])


def main():
    setup_logging()
    logger.info("Iniciando Utilitario de Rede v%s", VERSION)
    sys.excepthook = handle_exception
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(get_resource_path("assets", "icon.png")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
