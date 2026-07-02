_TIMEOUT_KEYWORDS = ("esgotado o tempo limite", "request timed out")


def build_tracert_command(host: str, resolve_hostnames: bool = False) -> list[str]:
    args = ["tracert"]
    if not resolve_hostnames:
        args.append("-d")
    args.append(host)
    return args


def is_timeout_line(line: str) -> bool:
    lowered = line.lower()
    return any(keyword in lowered for keyword in _TIMEOUT_KEYWORDS)
