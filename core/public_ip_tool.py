import urllib.request


def get_public_ip(timeout: float = 5.0) -> str:
    with urllib.request.urlopen("https://api.ipify.org", timeout=timeout) as response:
        return response.read().decode("utf-8").strip()
