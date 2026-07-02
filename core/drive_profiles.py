import json
import os

from core.portable_storage import get_base_dir


def _get_profiles_path() -> str:
    return os.path.join(get_base_dir(), "drive_profiles.json")


def load_profiles() -> list[dict]:
    path = _get_profiles_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profiles(profiles: list[dict]):
    with open(_get_profiles_path(), "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


def add_profile(profile: dict) -> list[dict]:
    profiles = [p for p in load_profiles() if p["name"] != profile["name"]]
    profiles.append(profile)
    save_profiles(profiles)
    return profiles


def delete_profile(name: str) -> list[dict]:
    profiles = [p for p in load_profiles() if p["name"] != name]
    save_profiles(profiles)
    return profiles
