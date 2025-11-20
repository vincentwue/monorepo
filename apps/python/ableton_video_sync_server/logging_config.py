import logging
from logging.config import dictConfig
from pathlib import Path

LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE_PATH = LOGS_DIR / "server.log"

def setup_logging():
    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            }
        },
        "handlers": {
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "standard",
            },
            "file": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "standard",
                "filename": str(LOG_FILE_PATH),
                "maxBytes": 10_000_000,  # 10 MB
                "backupCount": 5,
                "encoding": "utf-8"
            },
        },
        "loggers": {
            "": {  # root logger (your app)
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": True
            },
            "uvicorn": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False
            },
            "uvicorn.error": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False
            },
            "uvicorn.access": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False
            },
        }
    })
