"""Comprueba que el backend (Servidor A) es accesible. Útil desde el Servidor B.

    python scripts/check_backend.py 192.168.1.50        # IP del Servidor A
    python scripts/check_backend.py 192.168.1.50 8000
"""
from __future__ import annotations

import sys

import httpx


def main() -> int:
    ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = sys.argv[2] if len(sys.argv) > 2 else "8000"
    url = f"http://{ip}:{port}/api/health"
    print(f"Probando {url} ...")
    try:
        r = httpx.get(url, timeout=5)
        print(f"  HTTP {r.status_code}: {r.text}")
        if r.status_code == 200 and r.json().get("status") == "ok":
            print("  [OK] El backend responde. La comunicación A<->B funciona.")
            return 0
        print("  [FALLO] Respuesta inesperada.")
        return 1
    except httpx.HTTPError as e:
        print(f"  [FALLO] No se pudo conectar: {e}")
        print("  Revisa: backend arrancado con --host 0.0.0.0, firewall del Servidor A (puerto 8000), IP correcta.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
