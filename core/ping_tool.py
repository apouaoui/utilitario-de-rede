import re

_TIME_RE = re.compile(r"(?:tempo|time)[<=](\d+)\s*ms", re.IGNORECASE)
_LOST_KEYWORDS = (
    "esgotado o tempo limite",
    "timed out",
    "unreachable",
    "inacessível",
    "inacessivel",
    "falha na transmiss",
)


def build_ping_command(host: str, count: int = 4, continuous: bool = False) -> list[str]:
    args = ["ping"]
    args += ["-t"] if continuous else ["-n", str(count)]
    args.append(host)
    return args


def parse_ping_line(line: str):
    match = _TIME_RE.search(line)
    if match:
        return {"received": True, "time_ms": int(match.group(1))}
    lowered = line.lower()
    if any(keyword in lowered for keyword in _LOST_KEYWORDS):
        return {"received": False}
    return None
