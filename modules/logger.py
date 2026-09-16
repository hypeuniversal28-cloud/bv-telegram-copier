import logging, sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name="copier"):
    logger = logging.getLogger(name)
    if logger.handlers: return logger
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(fmt="%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)
    Path("logs").mkdir(exist_ok=True)
    fh = RotatingFileHandler("logs/copier.log", maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(logging.Formatter(fmt="%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)
    return logger


log = get_logger()
