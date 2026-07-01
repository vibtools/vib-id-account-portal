"""Container runtime entry point."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.main:app",
        # Container listener must bind all interfaces.
        host="0.0.0.0",  # noqa: S104  # nosec B104
        port=8000,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        access_log=False,
        timeout_graceful_shutdown=20,
    )


if __name__ == "__main__":
    main()
