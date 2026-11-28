import ctypes
import json
import os
import subprocess
import time
from pathlib import Path
from tempfile import gettempdir
from tkinter import TclError
from urllib.request import urlopen

from erp_window import open_erp_window

PROJECT_DIR = Path(__file__).resolve().parent
PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
APP_DIR = Path(os.getenv("LOCALAPPDATA") or gettempdir()) / "PythonFitnessERP"
ERP_URL = "http://127.0.0.1:8002"


def api_ready(port: int, expected_route: str) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/openapi.json", timeout=0.7) as response:
            schema = json.load(response)
    except (OSError, ValueError):
        return False
    paths = schema.get("paths") if isinstance(schema, dict) else None
    return isinstance(paths, dict) and expected_route in paths


def start_api(module: str, port: int, expected_route: str) -> subprocess.Popen | None:
    if api_ready(port, expected_route):
        return None

    log_directory = APP_DIR / "Logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / f"{port}.log"
    environment = {
        **os.environ,
        "ORDER_API_URL": "http://127.0.0.1:8001",
        "ORDERS_DB_PATH": str(PROJECT_DIR / "orders_demo.sqlite3"),
        "ERP_DB_PATH": str(PROJECT_DIR / "erp_uebung.sqlite3"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [str(PYTHON), "-m", "uvicorn", module, "--host", "127.0.0.1", "--port", str(port)],
            cwd=PROJECT_DIR,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if api_ready(port, expected_route):
            return process
        if process.poll() is not None:
            break
        time.sleep(0.25)

    if process.poll() is None:
        process.terminate()
    raise RuntimeError(f"Der Dienst auf Port {port} konnte nicht starten.\n\nProtokoll: {log_path}")


def main() -> None:
    if not PYTHON.is_file():
        raise RuntimeError(f"Die Python-Umgebung fehlt.\n\nErwartet: {PYTHON}")

    started = []
    try:
        for module, port, route in (
            ("orders_uebung:app", 8001, "/orders/{order_id}"),
            ("erp_uebung:app", 8002, "/erp/orders"),
        ):
            process = start_api(module, port, route)
            if process is not None:
                started.append(process)

        open_erp_window(ERP_URL)
    except (OSError, RuntimeError, TclError):
        for process in reversed(started):
            if process.poll() is None:
                process.terminate()
        raise


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, TclError) as error:
        ctypes.windll.user32.MessageBoxW(None, str(error), "Python Fitness ERP", 0x10)
        raise SystemExit(1)
