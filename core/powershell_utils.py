import json
import os
import subprocess
import tempfile


def run_powershell_json(command: str):
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
