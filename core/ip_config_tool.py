import ipaddress
import socket
import subprocess

from core.console_utils import get_console_encoding
from core.powershell_utils import run_powershell_json


def list_interfaces():
    import psutil

    dhcp_data = run_powershell_json(
        "Get-NetIPInterface -AddressFamily IPv4 | "
        "Select-Object InterfaceAlias, Dhcp | ConvertTo-Json"
    )
    if isinstance(dhcp_data, dict):
        dhcp_data = [dhcp_data]
    dhcp_map = {item["InterfaceAlias"]: item["Dhcp"] == "Enabled" for item in dhcp_data}

    config_data = run_powershell_json(
        "Get-NetIPConfiguration | Select-Object InterfaceAlias, "
        '@{n="Gateway";e={$_.IPv4DefaultGateway.NextHop}}, '
        '@{n="Dns";e={($_.DNSServer | Where-Object {$_.AddressFamily -eq 2}).ServerAddresses -join ","}} '
        "| ConvertTo-Json"
    )
    if isinstance(config_data, dict):
        config_data = [config_data]
    config_map = {
        item["InterfaceAlias"]: (item.get("Gateway") or "", item.get("Dns") or "")
        for item in config_data
    }

    interfaces = []
    stats = psutil.net_if_stats()
    for name, addrs in psutil.net_if_addrs().items():
        ipv4 = next((a for a in addrs if a.family == socket.AF_INET), None)
        if not ipv4:
            continue
        gateway, dns = config_map.get(name, ("", ""))
        interfaces.append({
            "name": name,
            "ip": ipv4.address,
            "netmask": ipv4.netmask,
            "is_up": stats[name].isup if name in stats else False,
            "dhcp": dhcp_map.get(name, True),
            "gateway": gateway,
            "dns": dns,
        })
    return interfaces


def normalize_netmask(value: str) -> str:
    value = value.strip()
    stripped = value.lstrip("/")
    if stripped.isdigit() and 0 <= int(stripped) <= 32:
        return str(ipaddress.ip_network(f"0.0.0.0/{int(stripped)}").netmask)
    return value


def validate_static_config(ip: str, netmask: str, gateway: str = "", dns: str = ""):
    try:
        ipaddress.IPv4Address(ip)
    except ValueError:
        return "IP inválido."

    try:
        mask_int = int(ipaddress.IPv4Address(netmask))
    except ValueError:
        return "Máscara inválida."
    inverted = mask_int ^ 0xFFFFFFFF
    if (inverted & (inverted + 1)) != 0:
        return "Máscara inválida (deve ser contígua, ex: 255.255.255.0 ou /24)."

    if gateway:
        try:
            ipaddress.IPv4Address(gateway)
        except ValueError:
            return "Gateway inválido."

    if dns:
        try:
            ipaddress.IPv4Address(dns)
        except ValueError:
            return "DNS inválido."

    return None


def test_gateway(gateway: str, timeout_ms: int = 1000) -> bool:
    result = subprocess.run(
        ["ping", "-n", "1", "-w", str(timeout_ms), gateway],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return result.returncode == 0


def set_static_ip(name: str, ip: str, netmask: str, gateway: str = "", dns: str = ""):
    cmd = ["netsh", "interface", "ip", "set", "address", f"name={name}", "static", ip, netmask]
    if gateway:
        cmd.append(gateway)
    subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)

    dns_cmd = [
        "netsh", "interface", "ip", "set", "dns", f"name={name}", "static",
        dns if dns else "none",
    ]
    subprocess.run(dns_cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)


def list_extra_ips(name: str, primary_ip: str = "") -> list:
    data = run_powershell_json(
        f'Get-NetIPAddress -InterfaceAlias "{name}" -AddressFamily IPv4 | '
        "Select-Object IPAddress | ConvertTo-Json"
    )
    if isinstance(data, dict):
        data = [data]
    ips = [item["IPAddress"] for item in data if not item["IPAddress"].startswith("169.254.")]
    return [ip for ip in ips if ip != primary_ip]


def add_extra_ip(name: str, ip: str, netmask: str):
    cmd = ["netsh", "interface", "ip", "add", "address", f"name={name}", ip, netmask]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding=get_console_encoding(),
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Falha ao adicionar IP")


def remove_extra_ip(name: str, ip: str):
    cmd = ["netsh", "interface", "ip", "delete", "address", f"name={name}", ip]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding=get_console_encoding(),
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Falha ao remover IP")


def set_dhcp(name: str):
    subprocess.run(
        ["netsh", "interface", "ip", "set", "address", f"name={name}", "dhcp"],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    subprocess.run(
        ["netsh", "interface", "ip", "set", "dns", f"name={name}", "dhcp"],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
