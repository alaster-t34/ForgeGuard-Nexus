from __future__ import annotations

import httpx


class HttpTransport:
    def __init__(self, base_url: str, timeout_seconds: float = 8.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def publish(self, topic: str, payload: dict) -> None:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/{topic.lstrip('/')}",
                json=payload,
                headers={"User-Agent": "ForgeGuard-Edge/0.1"},
            )
            response.raise_for_status()
