import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from core.version import VERSION

REPO = "apouaoui/utilitario-de-rede"


def _parse_version(value: str):
    value = value.strip().lstrip("vV")
    return tuple(int(part) for part in value.split("."))


def check_for_update():
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            release = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise

    latest_version = release.get("tag_name", "")
    if not latest_version or _parse_version(latest_version) <= _parse_version(VERSION):
        return None

    asset = next((a for a in release.get("assets", []) if a["name"].endswith(".exe")), None)
    if not asset:
        return None

    return {"version": latest_version, "url": asset["browser_download_url"]}


def download_update(url: str, progress_callback=None) -> str:
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Atualizacao automatica so funciona na versao empacotada (.exe).")

    base_dir = os.path.dirname(sys.executable)
    new_path = os.path.join(base_dir, "UtilitarioDeRede_new.exe")

    with urllib.request.urlopen(url, timeout=30) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        with open(new_path, "wb") as f:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total:
                    progress_callback(downloaded, total)

    return new_path


def prepare_update_script(new_exe_path: str):
    """Write and launch the helper script that swaps the exe once this process exits.

    Does not exit the process itself - the caller must quit the Qt app from the
    main thread afterwards so the batch script (which waits for our exe to stop
    running) can complete the swap and relaunch.

    The script is launched via a one-off Scheduled Task instead of a plain child
    process: PyInstaller onefile builds run inside a Windows Job Object that kills
    all child processes the moment the main exe exits, so a normal subprocess
    (even with DETACHED_PROCESS/CREATE_BREAKAWAY_FROM_JOB) can get killed before
    it finishes. A task launched by the Task Scheduler service runs completely
    outside our process tree and survives.
    """
    current_exe = sys.executable
    process_name = os.path.basename(current_exe)
    base_dir = os.path.dirname(current_exe)
    script_path = os.path.join(base_dir, "_update.bat")
    task_name = "UtilitarioDeRedeUpdate"

    script = (
        "@echo off\r\n"
        ":wait\r\n"
        f'tasklist /FI "IMAGENAME eq {process_name}" 2>NUL | find /I "{process_name}" >NUL\r\n'
        'if "%ERRORLEVEL%"=="0" (\r\n'
        "    ping -n 2 127.0.0.1 > nul\r\n"
        "    goto wait\r\n"
        ")\r\n"
        f'move /y "{new_exe_path}" "{current_exe}"\r\n'
        f'start "" "{current_exe}"\r\n'
        f'schtasks /delete /tn "{task_name}" /f\r\n'
        'del "%~f0"\r\n'
    )
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    start_time = (datetime.now() + timedelta(minutes=2)).strftime("%H:%M")
    subprocess.run(
        [
            "schtasks", "/create", "/tn", task_name,
            "/tr", f'cmd /c "{script_path}"',
            "/sc", "once", "/st", start_time, "/f",
        ],
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=True,
    )
    subprocess.run(
        ["schtasks", "/run", "/tn", task_name],
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=True,
    )
