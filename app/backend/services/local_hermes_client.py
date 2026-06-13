from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

import httpx
import websockets
from websockets.exceptions import WebSocketException

logger = logging.getLogger(__name__)
HermesEventCallback = Callable[[str, dict[str, Any]], Awaitable[None] | None]


class LocalHermesError(RuntimeError):
    pass


@dataclass
class LocalHermesResult:
    text: str
    usage: dict[str, Any] | None
    session_id: str
    stored_session_id: str


def extract_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.S)
    if fenced:
        try:
            data = json.loads(fenced.group(1).strip())
            return data if isinstance(data, dict) else None
        except Exception:
            pass

    candidate = _extract_balanced_json_object(raw)
    if candidate:
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except Exception:
            pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


def _extract_balanced_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


async def _call_event_callback(callback: HermesEventCallback | None, event_type: str, payload: dict[str, Any]) -> None:
    if not callback:
        return
    try:
        maybe_awaitable = callback(event_type, payload)
        if asyncio.iscoroutine(maybe_awaitable):
            await maybe_awaitable
    except LocalHermesError:
        raise
    except Exception:
        logger.exception("Local Hermes event callback failed")


class LocalHermesClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (
            base_url
            or os.getenv("HERMES_AGENT_URL")
            or os.getenv("LOCAL_HERMES_URL")
            or "http://127.0.0.1:9120"
        ).rstrip("/")
        self.timeout = float(os.getenv("HERMES_AGENT_TIMEOUT") or os.getenv("LOCAL_HERMES_TIMEOUT") or "900")

    async def _session_token(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=4, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LocalHermesError("Hermes服务未启动") from exc
        match = re.search(r'window\.__HERMES_SESSION_TOKEN__="([^"]+)"', response.text or "")
        if not match:
            raise LocalHermesError("Hermes服务未返回会话Token")
        return match.group(1)

    def _ws_url(self, token: str) -> str:
        parsed = urlparse(self.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        netloc = parsed.netloc or "127.0.0.1:9120"
        return urlunparse((scheme, netloc, "/api/ws", "", f"token={quote(token)}", ""))

    async def run_prompt(
        self,
        prompt: str,
        *,
        title: str = "AlignX Hermes",
        cwd: str = "",
        on_event: HermesEventCallback | None = None,
    ) -> LocalHermesResult:
        token = await self._session_token()
        ws_url = self._ws_url(token)
        origin = self.base_url
        request_id = 1

        try:
            ws = await websockets.connect(ws_url, open_timeout=8, origin=origin, ping_interval=20, ping_timeout=20)
        except (OSError, TimeoutError, WebSocketException) as exc:
            raise LocalHermesError("Hermes服务未启动") from exc

        async with ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=8)
            except (asyncio.TimeoutError, WebSocketException) as exc:
                raise LocalHermesError("Hermes服务连接失败") from exc
            await ws.send(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": "session.create",
                        "params": {
                            "title": title,
                            "cwd": cwd or os.getcwd(),
                            "cols": 110,
                            "close_on_disconnect": True,
                        },
                    },
                    ensure_ascii=False,
                )
            )

            session_id = ""
            stored_session_id = ""
            while True:
                message = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                if message.get("id") == request_id:
                    result = message.get("result") or {}
                    session_id = str(result.get("session_id") or "")
                    stored_session_id = str(result.get("stored_session_id") or "")
                    break
            if not session_id:
                raise LocalHermesError("Hermes服务会话创建失败")
            await _call_event_callback(
                on_event,
                "session.created",
                {"session_id": session_id, "stored_session_id": stored_session_id},
            )

            request_id += 1
            await ws.send(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": "prompt.submit",
                        "params": {"session_id": session_id, "text": prompt},
                    },
                    ensure_ascii=False,
                )
            )

            deadline = asyncio.get_running_loop().time() + self.timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise LocalHermesError("Hermes服务分析超时")
                try:
                    raw_message = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 30))
                except asyncio.TimeoutError:
                    continue
                except WebSocketException as exc:
                    raise LocalHermesError("Hermes服务连接中断") from exc
                message = json.loads(raw_message)
                if message.get("method") != "event":
                    continue
                params = message.get("params") or {}
                event_session_id = str(params.get("session_id") or "")
                if event_session_id and event_session_id != session_id:
                    continue
                event_type = params.get("type")
                payload = params.get("payload") or {}
                if not isinstance(payload, dict):
                    payload = {"value": payload}
                await _call_event_callback(
                    on_event,
                    str(event_type or ""),
                    {**payload, "_session_id": session_id, "_stored_session_id": stored_session_id},
                )
                if event_type == "error":
                    raise LocalHermesError(str(payload.get("message") or payload))
                if event_type == "message.complete":
                    return LocalHermesResult(
                        text=str(payload.get("text") or ""),
                        usage=payload.get("usage") if isinstance(payload.get("usage"), dict) else None,
                        session_id=session_id,
                        stored_session_id=stored_session_id,
                    )

    async def run_json(
        self,
        prompt: str,
        *,
        title: str = "AlignX Hermes",
        cwd: str = "",
        on_event: HermesEventCallback | None = None,
    ) -> dict[str, Any]:
        result = await self.run_prompt(prompt, title=title, cwd=cwd, on_event=on_event)
        data = extract_json_object(result.text)
        if data is None:
            logger.info("Local Hermes returned non-json text: %s", result.text[:500])
            raise LocalHermesError("Hermes服务未返回结构化JSON")
        data.setdefault("_hermes_usage", result.usage or {})
        data.setdefault("_hermes_session_id", result.stored_session_id or result.session_id)
        return data
