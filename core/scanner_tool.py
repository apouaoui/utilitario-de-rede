import ipaddress
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.console_utils import get_console_encoding


def get_local_networks():
    import psutil

    networks = []
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                try:
                    net = ipaddress.ip_network(f"{addr.address}/{addr.netmask}", strict=False)
                except ValueError:
                    continue
                if net.num_addresses <= 1024:
                    networks.append((iface, addr.address, net))
    return networks


def _parse_range(part: str) -> list:
    start_str, end_str = (p.strip() for p in part.split("-", 1))
    start = ipaddress.IPv4Address(start_str)
    if "." in end_str:
        end = ipaddress.IPv4Address(end_str)
    else:
        prefix = ".".join(start_str.split(".")[:3])
        end = ipaddress.IPv4Address(f"{prefix}.{end_str}")
    if int(end) < int(start):
        raise ValueError(f"Intervalo inválido: {part}")
    return [ipaddress.IPv4Address(value) for value in range(int(start), int(end) + 1)]


def parse_targets(text: str) -> list:
    addresses = []
    seen = set()
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        raise ValueError("Informe ao menos uma rede ou intervalo.")
    for part in parts:
        if "-" in part and "/" not in part:
            candidates = _parse_range(part)
        else:
            candidates = list(ipaddress.ip_network(part, strict=False).hosts())
        for addr in candidates:
            if addr not in seen:
                seen.add(addr)
                addresses.append(addr)
    return addresses


def _ping_once(ip: str) -> bool:
    result = subprocess.run(
        ["ping", "-n", "1", "-w", "500", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return result.returncode == 0


def _read_arp_table() -> dict:
    table = {}
    try:
        output = subprocess.check_output(
            ["arp", "-a"],
            text=True,
            encoding=get_console_encoding(),
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.CalledProcessError:
        return table
    for line in output.splitlines():
        match = re.match(r"\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})", line)
        if match:
            table[match.group(1)] = match.group(2)
    return table


def _ping_sweep(targets: list, max_workers: int = 64, progress_callback=None, cancel_event=None):
    alive = set()
    total = len(targets)
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_ping_once, str(ip)): ip for ip in targets}
        for future in as_completed(futures):
            if cancel_event is not None and cancel_event.is_set():
                for pending in futures:
                    pending.cancel()
                break
            ip = futures[future]
            done += 1
            if progress_callback:
                progress_callback(done, total)
            if future.result():
                alive.add(ip)
    return targets, alive


def _resolve_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror, OSError):
        return ""


def scan_network(targets: list, max_workers: int = 64, progress_callback=None, cancel_event=None):
    _, alive = _ping_sweep(targets, max_workers, progress_callback, cancel_event)
    sorted_ips = sorted(alive)

    if cancel_event is not None and cancel_event.is_set():
        return [{"ip": str(ip), "mac": "", "hostname": ""} for ip in sorted_ips]

    arp_table = _read_arp_table()

    hostnames = {}
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(0.5)
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_resolve_hostname, str(ip)): ip for ip in sorted_ips}
            for future in as_completed(futures):
                hostnames[futures[future]] = future.result()
    finally:
        socket.setdefaulttimeout(previous_timeout)

    results = []
    for ip in sorted_ips:
        ip_str = str(ip)
        results.append({
            "ip": ip_str,
            "mac": arp_table.get(ip_str, ""),
            "hostname": hostnames.get(ip, ""),
        })
    return results


def find_free_ips(targets: list, max_workers: int = 64, progress_callback=None, cancel_event=None):
    all_targets, alive = _ping_sweep(targets, max_workers, progress_callback, cancel_event)
    return [str(ip) for ip in all_targets if ip not in alive]
