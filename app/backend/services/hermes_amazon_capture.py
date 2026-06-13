from __future__ import annotations

import logging
import os
import re
from typing import Any

from services.local_hermes_client import LocalHermesClient, LocalHermesError

logger = logging.getLogger(__name__)


MARKETPLACE_HOSTS = {
    "US": "www.amazon.com",
    "UK": "www.amazon.co.uk",
    "CA": "www.amazon.ca",
    "DE": "www.amazon.de",
}


def amazon_product_url(asin: str, marketplace: str = "US") -> str:
    host = MARKETPLACE_HOSTS.get((marketplace or "US").upper(), "www.amazon.com")
    return f"https://{host}/dp/{asin.strip().upper()}"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [line.strip() for line in re.split(r"[\n;]+", value) if line.strip()]
    return []


def _build_product_capture_prompt(asin: str, marketplace: str) -> str:
    url = amazon_product_url(asin, marketplace)
    return "\n".join(
        [
            "你是 AlignX 的 Amazon 页面采集执行器。",
            "任务只限于用 Hermes 内置 Browserbase/browser_* 浏览器工具打开指定 Amazon 商品页并返回页面可见字段。",
            f"ASIN：{asin}",
            f"站点：{marketplace}",
            f"商品页：{url}",
            "",
            "执行规则：",
            "1. 必须使用 Browserbase/browser_* 浏览器工具打开商品页、等待页面可见、滚动读取页面。",
            "2. 优先用浏览器快照和视觉识别读取可见页面，模拟真人浏览节奏；页面懒加载时先滚动再读取。",
            "3. 禁止使用 execute_code、terminal、curl、HTML解析、本地脚本、文件工具、web_search。",
            "4. 不登录、不绕过验证码、不访问账号/订单/地址/支付等私有数据。",
            "5. 只采集页面可见且能确认属于该ASIN的数据；看不到的字段填空字符串、空数组、false或0。",
            "6. 不猜测、不补虚构数据、不写模型名或供应商名。",
            "7. 只返回一个JSON对象，不要Markdown，不要代码块，不要解释。",
            "",
            "输出JSON Schema：",
            """{
  "asin_verified": "",
  "title": "",
  "brand": "",
  "category": "",
  "price": "",
  "price_currency": "",
  "rating": "",
  "review_count": "",
  "bsr_rank": "",
  "bsr_category": "",
  "date_first_available": "",
  "availability": "",
  "stock_status": "",
  "coupon": "",
  "deal_status": "",
  "bullet_points": [],
  "product_details": {},
  "image_count": 0,
  "image_urls": [],
  "has_video": false,
  "has_a_plus": false,
  "aplus_content": "",
  "aplus_image_count": 0,
  "aplus_image_urls": [],
  "bought_count": "",
  "seller_type": "",
  "rating_histogram": {},
  "low_star_reviews": [],
  "review_samples": [],
  "capture_quality": {
    "confidence_level": "low|medium|high",
    "missing_fields": []
  }
}""",
        ]
    )


def normalize_hermes_product_capture(raw: dict[str, Any], asin: str, marketplace: str) -> dict[str, Any]:
    verified = _text(raw.get("asin_verified") or raw.get("asin")).upper()
    title = _text(raw.get("title"))
    scrape_success = bool(title) and (not verified or verified == asin.upper())
    data = {
        "scrape_success": scrape_success,
        "data_source": "hermes_browserbase" if scrape_success else "hermes_browserbase_incomplete",
        "asin": asin.upper(),
        "marketplace": (marketplace or "US").upper(),
        "title": title,
        "brand": _text(raw.get("brand")),
        "category": _text(raw.get("category")),
        "price": _text(raw.get("price")),
        "price_currency": _text(raw.get("price_currency")),
        "rating": _text(raw.get("rating")),
        "review_count": _text(raw.get("review_count")),
        "bsr_rank": _text(raw.get("bsr_rank")),
        "bsr_category": _text(raw.get("bsr_category")),
        "date_first_available": _text(raw.get("date_first_available")),
        "availability": _text(raw.get("availability")),
        "stock_status": _text(raw.get("stock_status") or "unknown"),
        "coupon": _text(raw.get("coupon")),
        "deal_status": _text(raw.get("deal_status")),
        "bullet_points": [str(item).strip() for item in _list(raw.get("bullet_points")) if str(item).strip()],
        "product_details": raw.get("product_details") if isinstance(raw.get("product_details"), dict) else {},
        "image_count": int(raw.get("image_count") or 0) if str(raw.get("image_count") or "0").isdigit() else 0,
        "image_urls": [str(item).strip() for item in _list(raw.get("image_urls")) if str(item).strip()],
        "has_video": bool(raw.get("has_video")),
        "has_a_plus": bool(raw.get("has_a_plus")),
        "aplus_content": _text(raw.get("aplus_content")),
        "aplus_image_count": int(raw.get("aplus_image_count") or 0) if str(raw.get("aplus_image_count") or "0").isdigit() else 0,
        "aplus_image_urls": [str(item).strip() for item in _list(raw.get("aplus_image_urls")) if str(item).strip()],
        "bought_count": _text(raw.get("bought_count")),
        "seller_type": _text(raw.get("seller_type")),
        "rating_histogram": raw.get("rating_histogram") if isinstance(raw.get("rating_histogram"), dict) else {},
        "low_star_reviews": _list(raw.get("low_star_reviews")),
        "review_samples": _list(raw.get("review_samples")),
        "capture_quality": raw.get("capture_quality") if isinstance(raw.get("capture_quality"), dict) else {},
        "_hermes_session_id": raw.get("_hermes_session_id"),
    }
    if not data["capture_quality"]:
        data["capture_quality"] = {
            "confidence_level": "medium" if scrape_success else "low",
            "missing_fields": [],
        }
    return data


async def scrape_amazon_product_via_hermes(
    asin: str,
    marketplace: str = "US",
    *,
    on_event: Any = None,
) -> dict[str, Any]:
    asin = (asin or "").strip().upper()
    marketplace = (marketplace or "US").upper()
    if not re.fullmatch(r"[A-Z0-9]{10}", asin):
        return {"scrape_success": False, "data_source": "hermes_browserbase_invalid_asin", "asin": asin}
    try:
        raw = await LocalHermesClient().run_json(
            _build_product_capture_prompt(asin, marketplace),
            title=f"AlignX Amazon采集 {asin}",
            cwd=os.getcwd(),
            on_event=on_event,
        )
        return normalize_hermes_product_capture(raw, asin, marketplace)
    except LocalHermesError as exc:
        logger.info("Hermes Amazon capture failed for %s: %s", asin, exc)
        return {
            "scrape_success": False,
            "data_source": "hermes_browserbase_failed",
            "asin": asin,
            "marketplace": marketplace,
            "error": str(exc),
        }
