import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from services.amazon_scraper import (
    ACCEPT_LANG,
    MARKETPLACE_DOMAINS,
    _build_desktop_headers,
    _clean_text,
    _is_captcha_page,
    _parse_product_page,
)

logger = logging.getLogger(__name__)

SCRAPLING_TOP40_RULES = [
    "Only process a keyword and marketplace explicitly submitted by the user.",
    "Capture a Top40 search snapshot in four batches: 1-10, 11-20, 21-30, 31-40.",
    "A single request must visit no more than 10 listing detail pages.",
    "Do not expand keywords, crawl recommendations, or continue beyond Top40.",
    "Keep Sponsored listings in rank order and mark isSponsored=true.",
    "Extract only public listing/search fields visible on the page.",
    "Do not read account, order, address, payment, or other private user data.",
    "If captcha, robot check, login wall, or abnormal access appears, stop and return blocked or partial.",
    "Do not attempt to bypass captcha, login walls, or access restrictions.",
    "Return raw structured JSON only; cleaning and market analysis belong to the AI analysis layer.",
]


def _marketplace_url(marketplace: str) -> tuple[str, str]:
    code = (marketplace or "US").upper()
    return code, MARKETPLACE_DOMAINS.get(code, MARKETPLACE_DOMAINS["US"])


def _price_to_number(price_text: str) -> float | None:
    match = re.search(r"[\d,.]+", price_text or "")
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _text_number(text: str) -> int | None:
    match = re.search(r"[\d,]+", text or "")
    if not match:
        return None
    try:
        return int(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _rating_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", text or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_search_item(card: Any, domain: str, rank: int) -> dict[str, Any] | None:
    asin = (card.get("data-asin") or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{10}", asin):
        return None

    title_el = card.select_one("h2 span") or card.select_one("h2 a") or card.select_one("[data-cy='title-recipe'] span")
    link_el = card.select_one("h2 a[href]") or card.select_one("a.a-link-normal.s-no-outline[href]")
    image_el = card.select_one("img.s-image")
    rating_el = card.select_one("span.a-icon-alt")
    review_el = card.select_one("a[href*='customerReviews'] span.a-size-base") or card.select_one("span[aria-label*='ratings']")
    price_el = card.select_one(".a-price .a-offscreen")
    sponsored_blob = _clean_text(card.get_text(" ", strip=True)).lower()

    href = link_el.get("href") if link_el else f"/dp/{asin}"
    url = href if href.startswith("http") else f"https://{domain}{href}"
    url = url.split("/ref=")[0] if "/ref=" in url else url

    price_text = _clean_text(price_el.get_text(" ", strip=True)) if price_el else ""
    rating_text = _clean_text(rating_el.get_text(" ", strip=True)) if rating_el else ""
    review_text = _clean_text(review_el.get_text(" ", strip=True)) if review_el else ""

    return {
        "searchRank": rank,
        "asin": asin,
        "url": url,
        "title": _clean_text(title_el.get_text(" ", strip=True)) if title_el else "",
        "price": _price_to_number(price_text),
        "priceText": price_text,
        "searchPrice": _price_to_number(price_text),
        "searchPriceText": price_text,
        "detailPrice": None,
        "detailPriceText": "",
        "priceSource": "search_result" if price_text else "missing",
        "priceStatus": "search_price" if price_text else "missing",
        "rating": _rating_number(rating_text),
        "reviewCount": _text_number(review_text),
        "imageUrl": image_el.get("src", "") if image_el else "",
        "isSponsored": "sponsored" in sponsored_blob or "赞助" in sponsored_blob,
        "source": "search_result",
    }


async def _fetch_html(url: str, marketplace: str, referer: str = "") -> tuple[int, str]:
    try:
        from scrapling.fetchers import AsyncFetcher
    except ImportError as exc:
        raise RuntimeError("Scrapling is not installed in the backend environment") from exc

    lang = ACCEPT_LANG.get(marketplace, "en-US,en;q=0.9")
    headers = _build_desktop_headers(lang)
    if referer:
        headers["Referer"] = referer

    response = await AsyncFetcher.get(
        url,
        headers=headers,
        timeout=20,
        retries=1,
        follow_redirects=True,
        stealthy_headers=True,
    )
    html = getattr(response, "html_content", None) or getattr(response, "body", b"")
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="ignore")
    return int(getattr(response, "status", 0) or 0), str(html or "")


def _parse_search_results(html: str, domain: str, start_rank: int = 1) -> list[dict[str, Any]]:
    if _is_captcha_page(html):
        return []
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    rank = start_rank
    for card in soup.select("div[data-component-type='s-search-result'][data-asin]"):
        item = _extract_search_item(card, domain, rank)
        if not item or item["asin"] in seen:
            continue
        seen.add(item["asin"])
        items.append(item)
        rank += 1
    return items


async def _fetch_search_snapshot(keyword: str, marketplace: str, limit: int) -> tuple[str, list[dict[str, Any]], list[str]]:
    marketplace, domain = _marketplace_url(marketplace)
    errors: list[str] = []
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for page in range(1, 5):
        search_url = f"https://{domain}/s?k={quote_plus(keyword)}&page={page}"
        try:
            status, html = await _fetch_html(search_url, marketplace)
        except Exception as exc:
            errors.append(f"search_page_{page}: {exc}")
            break

        if status >= 400:
            errors.append(f"search_page_{page}: http_{status}")
            break
        if _is_captcha_page(html):
            return "blocked", items, errors + [f"search_page_{page}: captcha_or_robot_check"]

        for item in _parse_search_results(html, domain, len(items) + 1):
            if item["asin"] in seen:
                continue
            seen.add(item["asin"])
            items.append(item)
            if len(items) >= limit:
                return "ok", items, errors

        await asyncio.sleep(random.uniform(1.0, 2.0))

    return ("ok" if items else "error"), items, errors


async def _enrich_detail(item: dict[str, Any], marketplace: str) -> dict[str, Any]:
    try:
        status, html = await _fetch_html(item["url"], marketplace)
        if status >= 400:
            return {**item, "status": "error", "error": f"http_{status}", "priceStatus": item.get("priceStatus") or "detail_error"}
        if _is_captcha_page(html):
            return {**item, "status": "blocked", "error": "captcha_or_robot_check", "priceStatus": item.get("priceStatus") or "blocked"}
        parsed = _parse_product_page(html, marketplace) or {}
        if not parsed:
            return {**item, "status": "partial", "error": "detail_parse_failed", "priceStatus": item.get("priceStatus") or "detail_parse_failed"}

        detail_price_text = str(parsed.get("price") or "")
        detail_price = _price_to_number(detail_price_text)
        search_price = item.get("searchPrice") if item.get("searchPrice") is not None else item.get("price")
        search_price_text = str(item.get("searchPriceText") or item.get("priceText") or "")
        final_price = detail_price if detail_price is not None else search_price
        final_price_text = detail_price_text or search_price_text
        if detail_price is not None:
            price_source = "detail_page"
            price_status = "detail_price"
        elif search_price is not None:
            price_source = "search_result"
            price_status = "search_price_fallback"
        else:
            price_source = "missing"
            price_status = "missing"

        return {
            **item,
            "title": parsed.get("title") or item.get("title") or "",
            "brand": parsed.get("brand") or "",
            "category": parsed.get("category") or "",
            "sellerType": parsed.get("seller_type") or "",
            "price": final_price,
            "priceText": final_price_text,
            "searchPrice": search_price,
            "searchPriceText": search_price_text,
            "detailPrice": detail_price,
            "detailPriceText": detail_price_text,
            "priceSource": price_source,
            "priceStatus": price_status,
            "priceCurrency": parsed.get("price_currency") or "",
            "couponText": parsed.get("coupon") or "",
            "dealStatus": parsed.get("deal_status") or "",
            "rating": _rating_number(str(parsed.get("rating") or "")) or item.get("rating"),
            "reviewCount": _text_number(str(parsed.get("review_count") or "")) or item.get("reviewCount"),
            "availability": "",
            "mainImageUrl": (parsed.get("image_urls") or [item.get("imageUrl", "")])[0],
            "imageUrls": parsed.get("image_urls") or [],
            "bulletPoints": parsed.get("bullet_points") or [],
            "bestSellerRankText": parsed.get("bsr_rank") or "",
            "bestSellerCategory": parsed.get("bsr_category") or "",
            "boughtCount": parsed.get("bought_count") or "",
            "hasAPlus": bool(parsed.get("has_a_plus")),
            "hasVideo": bool(parsed.get("has_video")),
            "status": "ok",
            "error": "",
        }
    except Exception as exc:
        logger.info("Scrapling detail fetch failed for %s: %s", item.get("asin"), exc)
        return {**item, "status": "error", "error": str(exc)[:180], "priceStatus": item.get("priceStatus") or "detail_error"}


async def capture_top40_batch(keyword: str, marketplace: str = "US", batch_index: int = 1) -> dict[str, Any]:
    keyword = _clean_text(keyword)
    if not keyword:
        raise ValueError("keyword is required")
    if batch_index < 1 or batch_index > 4:
        raise ValueError("batch_index must be between 1 and 4")

    marketplace, _domain = _marketplace_url(marketplace)
    rank_start = (batch_index - 1) * 10 + 1
    rank_end = batch_index * 10
    snapshot_status, snapshot_items, errors = await _fetch_search_snapshot(keyword, marketplace, rank_end)
    batch_items = [item for item in snapshot_items if rank_start <= item["searchRank"] <= rank_end][:10]

    captured: list[dict[str, Any]] = []
    blocked = snapshot_status == "blocked"
    for index, item in enumerate(batch_items, start=1):
        enriched = await _enrich_detail(item, marketplace)
        captured.append(enriched)
        if enriched.get("status") == "blocked":
            blocked = True
            errors.append(f"detail_{item['asin']}: captcha_or_robot_check")
            break
        if index < len(batch_items):
            await asyncio.sleep(random.uniform(1.5, 3.5))

    ok_count = sum(1 for item in captured if item.get("status") == "ok")
    if blocked and ok_count == 0:
        status = "blocked"
    elif blocked or ok_count < len(batch_items):
        status = "partial"
    else:
        status = "ok"

    return {
        "marketplace": marketplace,
        "keyword": keyword,
        "batchIndex": batch_index,
        "rankRange": f"{rank_start}-{rank_end}",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "rules": SCRAPLING_TOP40_RULES,
        "items": captured,
        "errors": errors,
        "dataSource": "scrapling_top40_batch",
        "analysisNote": "Raw capture only. Cleaning, normalization, and market opportunity analysis must run in the backend AI layer.",
    }
