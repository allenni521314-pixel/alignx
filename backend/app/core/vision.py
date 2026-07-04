import base64
import asyncio
import httpx
import logging
import os
import struct
from typing import Optional, Dict, List, Any
from app.config import get_settings

settings = get_settings()
_logger = logging.getLogger(__name__)

MIN_IMAGE_DIMENSION = 28  # Qwen VL 系列模型的最小边长要求

QWEN_KEY = settings.qwen_api_key
if not QWEN_KEY:
    _qwen_key_file = os.path.join(os.path.dirname(__file__), "..", "..", ".qwen_key")
    if os.path.exists(_qwen_key_file):
        try:
            with open(_qwen_key_file) as f:
                QWEN_KEY = f.read().strip()
        except Exception:
            pass

_logger.debug("QWEN_KEY loaded: %s chars", len(QWEN_KEY) if QWEN_KEY else 0)

QWEN_BASE = settings.qwen_base_url
QWEN_MODEL = settings.qwen_model

LISTING_IMAGE_OCR_PROMPT = """识别这张图片上的所有可见文案，逐字提取。要求：保留原文语言、大小写、数字、符号；按从上到下从左到右顺序；看不清标[看不清]。如果没有可见文案，写"可见文案：暂无"。然后简要描述图片内容（产品、场景、配件等）。"""

def _image_data_url(image_data: str) -> str:
    image_data = (image_data or "").strip()
    if image_data.startswith("data:image/"):
        return image_data
    if "," in image_data and image_data.split(",", 1)[0].startswith("data:"):
        image_data = image_data.split(",", 1)[1].strip()

    mime = "image/jpeg"
    if image_data.startswith("iVBOR"):
        mime = "image/png"
    elif image_data.startswith("R0lG"):
        mime = "image/gif"
    elif image_data.startswith("UklGR"):
        mime = "image/webp"
    return f"data:{mime};base64,{image_data}"


def _decode_image_bytes(image_data: str) -> Optional[bytes]:
    """从 data URL 或裸 base64 字符串解出原始图片二进制。解不出来返回 None。"""
    raw = (image_data or "").strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=False)
    except Exception:
        return None


def _get_image_dimensions(data: bytes) -> Optional[tuple]:
    """零依赖解析常见图片格式（PNG/JPEG/GIF/WEBP）的宽高。解不出来返回 None（不阻断，交给下游 API 判断）。"""
    if not data or len(data) < 24:
        return None
    try:
        # PNG: 8字节签名 + IHDR chunk，宽高在偏移16-24
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            width, height = struct.unpack(">II", data[16:24])
            return (width, height)
        # GIF: 签名后6字节是宽高（小端）
        if data[:6] in (b"GIF87a", b"GIF89a"):
            width, height = struct.unpack("<HH", data[6:10])
            return (width, height)
        # WEBP (RIFF容器，VP8/VP8L/VP8X)
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            chunk = data[12:16]
            if chunk == b"VP8X" and len(data) >= 30:
                width = 1 + (data[24] | (data[25] << 8) | (data[26] << 16))
                height = 1 + (data[27] | (data[28] << 8) | (data[29] << 16))
                return (width, height)
            if chunk == b"VP8 " and len(data) >= 30:
                width, height = struct.unpack("<HH", data[26:30])
                return (width & 0x3FFF, height & 0x3FFF)
        # JPEG: 需要遍历 marker 找 SOF
        if data[:2] == b"\xff\xd8":
            i = 2
            n = len(data)
            while i < n - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    height, width = struct.unpack(">HH", data[i + 5:i + 9])
                    return (width, height)
                if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + seg_len
            return None
    except Exception:
        return None
    return None


def _image_too_small(image_data: str) -> bool:
    """预检查：图片宽或高小于模型最小要求时返回 True。解析失败时保守放行（返回 False），交给下游 API 自行判断。"""
    data = _decode_image_bytes(image_data)
    if not data:
        return False
    dims = _get_image_dimensions(data)
    if not dims:
        return False
    width, height = dims
    return width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION


def _build_listing_image_ocr_prompt(slot: str = "", product_context: str = "") -> str:
    context = product_context.strip()[:1500] if product_context else "暂无"
    return f"""{LISTING_IMAGE_OCR_PROMPT}
图片位置：{slot or '未设置'}
已知产品信息：{context}"""

async def _call_qwen_vision(image_b64: str, prompt: str, max_tokens: int = 200) -> str:
    if not QWEN_KEY:
        return ""
    if _image_too_small(image_b64):
        raise ValueError(f"图片尺寸过小（小于 {MIN_IMAGE_DIMENSION}px），无法识别")
    timeout = httpx.Timeout(30.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        resp = await client.post(
            f"{QWEN_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {QWEN_KEY}"},
            json={
                "model": QWEN_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": _image_data_url(image_b64)}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "choices" not in data:
            raise RuntimeError(str(data)[:500])
        return data["choices"][0]["message"]["content"].strip()


async def extract_text_from_images(image_urls: list, product_context: str = "", slots_by_url: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    if not image_urls or not QWEN_KEY:
        return {}
    results = {}
    errors = []  # type: list[str]
    timeout = httpx.Timeout(30.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        for url in image_urls[:7]:
            try:
                img_resp = await client.get(url)
                img_resp.raise_for_status()
                img_b64 = base64.b64encode(img_resp.content).decode()
                slot = slots_by_url.get(url, "") if slots_by_url else ""
                text = await _call_qwen_vision(img_b64, _build_listing_image_ocr_prompt(slot=slot, product_context=product_context), max_tokens=800)
                if text: results[url] = text
            except Exception as exc:
                errors.append(f"{url}: {exc!r}")
                if len(errors) >= 3 and not results: break
                continue
    if not results and errors: raise RuntimeError("; ".join(errors[:3]))
    return results


async def extract_text_from_image_url(url: str) -> str:
    results = await extract_text_from_images([url])
    return results.get(url, "")


async def extract_text_from_base64_list(items: list, product_context: str = "") -> list:
    """OCR uploaded images with the same single-image path used by listing analysis."""
    if not items or not QWEN_KEY:
        if not QWEN_KEY:
            _logger.warning("Qwen API key not configured — OCR skipped")
        return []

    normalized_items = [
        item for item in items
        if str(item.get("slot", "")).strip() and item.get("url")
    ]
    semaphore = asyncio.Semaphore(2)

    async def _guarded_process(item: dict) -> Optional[dict]:
        slot = str(item.get("slot", "")).strip()
        async with semaphore:
            result = await _process_single_item(item, product_context=product_context)
            if result:
                return result
            await asyncio.sleep(0.8)
            retry = await _process_single_item(item, product_context=product_context)
            if retry:
                return retry
            _logger.warning("OCR returned empty after retry for slot %s", slot)
            return None

    raw_results = await asyncio.gather(
        *(_guarded_process(item) for item in normalized_items),
        return_exceptions=True,
    )
    results: list[dict] = []
    for item, raw in zip(normalized_items, raw_results):
        if isinstance(raw, Exception):
            _logger.warning("OCR task failed for slot %s: %s", item.get("slot"), raw)
            continue
        if raw and raw.get("text"):
            results.append(raw)
    if len(results) < len(normalized_items):
        _logger.warning("OCR incomplete: %s/%s slots recognized", len(results), len(normalized_items))
    return results


async def _process_single_item(item: dict, product_context: str = "") -> Optional[dict]:
    slot = str(item.get("slot", "")).strip()
    image_data = item.get("url", "")
    if not slot or not image_data:
        return None
    try:
        text = await _call_qwen_vision(
            image_data,
            _build_listing_image_ocr_prompt(slot=slot, product_context=product_context),
            max_tokens=1200,
        )
    except Exception as exc:
        _logger.warning("Single OCR failed for slot %s: %s", slot, exc)
        return None
    text = (text or "").strip()
    if not text:
        return None
    return {"slot": slot, "text": text}
