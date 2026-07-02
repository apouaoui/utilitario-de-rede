import shutil
import string
import subprocess

from core.console_utils import get_console_encoding
from core.powershell_utils import run_powershell_json

_STATUS_LABELS = {
    0: "OK",
    1: "Pausado",
    2: "Desconectado",
    3: "Erro de rede",
    4: "Conectando",
    5: "Reconectando",
    6: "Indisponível",
}


def get_drive_space(letter: str) -> str:
    try:
        usage = shutil.disk_usage(f"{letter.rstrip(':')}:\\")
    except OSError:
        return "-"
    free_gb = usage.free / 1_000_000_000
    total_gb = usage.total / 1_000_000_000
    return f"{free_gb:.1f} GB livres de {total_gb:.1f} GB"


def list_mapped_drives():
    data = run_powershell_json(
        "Get-SmbMapping | Select-Object LocalPath, RemotePath, Status | ConvertTo-Json"
    )
    if isinstance(data, dict):
        data = [data]
    drives = []
    for item in data:
        if not item.get("LocalPath"):
            continue
        letter = item["LocalPath"]
        status_code = item["Status"]
        drives.append({
            "letter": letter,
            "path": item["RemotePath"],
            "status": _STATUS_LABELS.get(status_code, str(status_code)),
            "space": get_drive_space(letter) if status_code == 0 else "-",
        })
    return drives


def available_drive_letters():
    import psutil

    used = {drive["letter"].rstrip(":").upper() for drive in list_mapped_drives()}
    used |= {
        partition.device.rstrip("\\").rstrip(":").upper()
        for partition in psutil.disk_partitions(all=False)
    }
    return [f"{letter}:" for letter in string.ascii_uppercase if letter not in used]


def map_drive(letter: str, path: str, username: str = "", password: str = "", persist: bool = True):
    cmd = ["net", "use", f"{letter}:", path]
    if username:
        cmd.append(f"/user:{username}")
    if password:
        cmd.append(password)
    cmd.append("/persistent:yes" if persist else "/persistent:no")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding=get_console_encoding(),
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Falha ao mapear unidade")


def reconnect_drive(letter: str, path: str):
    map_drive(letter, path, persist=True)


def disconnect_drive(letter: str):
    result = subprocess.run(
        ["net", "use", f"{letter}:", "/delete", "/yes"],
        capture_output=True,
        text=True,
        encoding=get_console_encoding(),
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Falha ao desconectar unidade")
