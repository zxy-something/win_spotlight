import os
import tempfile
import time
from pathlib import Path

_LOG_DIR = Path(os.getenv("LOCALAPPDATA") or tempfile.gettempdir()) / "Spotlight"
_LOG_PATH = _LOG_DIR / "spotlight.log"


def log(message: str) -> None:
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        if _LOG_PATH.exists() and _LOG_PATH.stat().st_size > 512_000:
            _LOG_PATH.unlink()
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}\n")
    except OSError:
        pass
