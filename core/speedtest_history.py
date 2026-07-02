import json
import os

from core.portable_storage import get_base_dir


def _get_history_path() -> str:
    return os.path.join(get_base_dir(), "speedtest_history.json")


def load_history() -> list[dict]:
    path = _get_history_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def add_result(entry: dict, max_entries: int = 50) -> list[dict]:
    history = load_history()
    history.append(entry)
    history = history[-max_entries:]
    with open(_get_history_path(), "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return history


def clear_history():
    with open(_get_history_path(), "w", encoding="utf-8") as f:
        json.dump([], f)
