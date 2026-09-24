"""Check API readiness through loopback using an allowed production Host."""

import http.client
import re

from app.core.config import Settings, get_settings


def healthcheck_host(settings: Settings) -> str:
    for allowed in settings.allowed_host_list:
        host = f"health{allowed[1:]}" if allowed.startswith("*.") else allowed
        if re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
            return host
    raise ValueError("ALLOWED_HOSTS needs an exact host or a valid subdomain wildcard")


def main() -> None:
    connection = http.client.HTTPConnection("127.0.0.1", 8000, timeout=5)
    try:
        connection.request("GET", "/ready", headers={"Host": healthcheck_host(get_settings())})
        response = connection.getresponse()
        if response.status != 200:
            raise SystemExit(f"API readiness returned HTTP {response.status}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
