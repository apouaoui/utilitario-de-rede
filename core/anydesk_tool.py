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

    return cleared
