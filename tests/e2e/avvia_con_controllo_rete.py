"""Avvia `streamlit run app.py` registrando ogni connessione di rete che il
processo Python prova ad aprire verso indirizzi diversi da questo computer.

Uso: python tests/e2e/avvia_con_controllo_rete.py <file_log> <porta>
"""
import ipaddress
import socket
import sys
from pathlib import Path

LOG = Path(sys.argv[1])
PORT = sys.argv[2]
ROOT = Path(__file__).resolve().parents[2]


def _locale(host) -> bool:
    if host in (None, "", "localhost"):
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


def hook(event, args):
    if event == "socket.connect":
        sock, addr = args
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not _locale(addr[0]):
            with LOG.open("a") as f:
                f.write(f"connect {addr!r}\n")
    elif event == "socket.getaddrinfo":
        if not _locale(args[0]):
            with LOG.open("a") as f:
                f.write(f"getaddrinfo {args[0]!r}\n")


sys.addaudithook(hook)
LOG.write_text("")
sys.argv = ["streamlit", "run", str(ROOT / "app.py"), "--server.port", PORT, "--server.headless", "true"]
from streamlit.web.cli import main  # noqa: E402

main()
