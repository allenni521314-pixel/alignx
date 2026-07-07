from __future__ import annotations

import os

import httpx


def main() -> None:
    api_base = os.getenv("ALIGNX_API_BASE", "https://alignxagent-api.onrender.com").rstrip("/")
    token = os.getenv("REPORT_PUSH_TOKEN", "")
    if not token:
        raise SystemExit("REPORT_PUSH_TOKEN 未设置")

    response = httpx.post(
        f"{api_base}/api/v1/reports/daily-push",
        headers={"X-Report-Push-Token": token},
        timeout=120,
    )
    response.raise_for_status()
    print(response.text)


if __name__ == "__main__":
    main()
