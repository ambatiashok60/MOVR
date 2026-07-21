import contextvars
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from time import monotonic


request_id_var = contextvars.ContextVar("request_id", default="-")
session_id_var = contextvars.ContextVar("session_id", default="-")


class PrettyFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[2m", logging.INFO: "\033[36m",
        logging.WARNING: "\033[33m", logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }

    def __init__(self, color: bool):
        super().__init__(datefmt="%H:%M:%S")
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        level = record.levelname.ljust(7)
        prefix = f"{timestamp} {level} req={request_id_var.get()} session={session_id_var.get()}"
        line = f"{prefix}  {record.getMessage()}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        if self.color:
            return f"{self.COLORS.get(record.levelno, '')}{line}\033[0m"
        return line


class DailyTextFileHandler(logging.Handler):
    """Append logs to one UTF-8 text file per local calendar day."""

    def __init__(self, directory: Path):
        super().__init__()
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.day = ""
        self.stream = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            day = datetime.now().astimezone().date().isoformat()
            if day != self.day:
                if self.stream:
                    self.stream.close()
                self.day = day
                self.stream = (self.directory / f"backend-{day}.txt").open("a", encoding="utf-8")
            self.stream.write(self.format(record) + "\n")
            self.stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None
        super().close()


def configure_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    logger = logging.getLogger("agentic-workspace-chat")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    color = sys.stdout.isatty() and os.getenv("NO_COLOR") is None
    handler.setFormatter(PrettyFormatter(color))
    logger.addHandler(handler)
    file_handler = DailyTextFileHandler(log_dir or Path(__file__).resolve().parents[1] / "logs")
    file_handler.setFormatter(PrettyFormatter(False))
    logger.addHandler(file_handler)


class elapsed:
    def __enter__(self):
        self.started = monotonic()
        return self

    @property
    def ms(self) -> int:
        return round((monotonic() - self.started) * 1000)

    def __exit__(self, *_args):
        return False
