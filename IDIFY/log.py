import logging
import os
from logging.handlers import RotatingFileHandler

_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(_log_dir, exist_ok=True)
_log_file = os.path.join(_log_dir, "vidjo.log")

import sys

try:
    if sys.stdout and sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr and sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

_fmt = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d:%(funcName)s] - %(message)s"

# Basic config will now use the utf-8 reconfigured stdout/stderr
logging.basicConfig(level=logging.INFO, format=_fmt)

_file_handler = RotatingFileHandler(_log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(_fmt))

logger = logging.getLogger("download_blob_videos")
logger.addHandler(_file_handler)
