import os
import shutil
import subprocess
import time

from core.admin_utils import is_admin


def _kill_anydesk():
    subprocess.run(
        ["taskkill", "/IM", "AnyDesk.exe", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _find_msi_installers() -> list:
    user_profile = os.environ.get("USERPROFILE", "")
    search_dirs = [
        os.path.join(user_profile, "Downloads"),
        os.path.join(user_profile, "Desktop"),
        os.environ.get("TEMP", ""),
        os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "AnyDesk"),
    ]

    found = []
    for directory in search_dirs:
        if not directory or not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if name.lower().endswith(".msi") and "anydesk" in name.lower():
                found.append(os.path.join(directory, name))
    return found


def clear_anydesk_data() -> list:
    _kill_anydesk()
    time.sleep(1)

    cleared = []

    appdata = os.environ.get("APPDATA")
    if appdata:
        path = os.path.join(appdata, "AnyDesk")
        if os.path.isdir(path):
            shutil.rmtree(path)
            cleared.append(path)

    if is_admin():
        programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        path = os.path.join(programdata, "AnyDesk")
        if os.path.isdir(path):
            shutil.rmtree(path)
            cleared.append(path)

    for msi_path in _find_msi_installers():
        os.remove(msi_path)
        cleared.append(msi_path)

    return cleared
