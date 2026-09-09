from __future__ import annotations

import json
import os
import socket


def main() -> None:
    if os.getuid() != 10001:
        raise RuntimeError("unexpected control client uid")
    endpoint_ip = socket.gethostbyname("host-canary-r2.test")
    with socket.create_connection((endpoint_ip, 49175), timeout=2) as connection:
        response = connection.recv(32)
    if not response.startswith(b"R2_HOST_CANARY"):
        raise RuntimeError("host gateway control endpoint returned an unexpected response")
    print(
        json.dumps(
            {
                "endpoint_ip": endpoint_ip,
                "port": 49175,
                "response": "R2_HOST_CANARY",
                "uid": os.getuid(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
