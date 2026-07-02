import logging
import os
from logging.handlers import RotatingFileHandler

from core.portable_storage import get_base_dir


def setup_logging():
    log_path = os.path.join(get_base_dir(), "utilitario_rede.log")
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    return logger
