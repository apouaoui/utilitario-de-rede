import json
import os
import subprocess
import tempfile
import time


def _run_powershell_json_once(command: str):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        full_command = f"{command} | Out-File -FilePath '{path}' -Encoding utf8"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", full_command],
            capture_output=True,
            text=True,
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Falha ao executar PowerShell")
        with open(path, "r", encoding="utf-8-sig") as f:
            raw = f.read().strip()
        return json.loads(raw) if raw else []
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def run_powershell_json(command: str, retries: int = 2, retry_delay: float = 1.0):
    last_error = None
    for attempt in range(retries + 1):
        try:
            return _run_powershell_json_once(command)
        except RuntimeError as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_delay)
    raise last_error
