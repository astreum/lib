import os
import platform
from pathlib import Path


def ensure_data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    target = base / "Astreum" / "lib-py"
    for folder in ("accounts",):
        (target / folder).mkdir(parents=True, exist_ok=True)
    return target
