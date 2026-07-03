import time
import urllib.error
import urllib.request


def get_public_ip(timeout: float = 5.0, retries: int = 2, retry_delay: float = 2.0) -> str:
    last_error = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen("https://api.ipify.org", timeout=timeout) as response:
                return response.read().decode("utf-8").strip()
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_delay)
    raise last_error
