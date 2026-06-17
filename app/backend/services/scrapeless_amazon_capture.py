from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup

from services.amazon_scraper import MARKETPLACE_DOMAINS, _clean_text, _parse_product_page

logger = logging.getLogger(__name__)

SCRAPERAPI_TIMEOUT_SECONDS = float(
    os.getenv("SCRAPERAPI_TIMEOUT_SECONDS")
    or "300"
)
AMAZON_CAPTURE_PROVIDER = (os.getenv("AMAZON_CAPTURE_PROVIDER") or "scraperapi").strip().lower()
SCRAPERAPI_BASE_URL = (os.getenv("SCRAPERAPI_BASE_URL") or "https://api.scraperapi.com").rstrip("/")
SCRAPERAPI_PREMIUM = (os.getenv("SCRAPERAPI_PREMIUM") or "false").strip().lower() == "true"
SCRAPERAPI_ULTRA_PREMIUM = (os.getenv("SCRAPERAPI_ULTRA_PREMIUM") or "false").strip().lower() == "true"

logging.getLogger("httpx").setLevel(logging.WARNING)


class ScrapelessCaptureError(RuntimeError):
    pass


def _api_key() -> str:
    return (os.getenv("SCRAPERAPI_KEY") or "").strip()


def _marketplace_domain(marketplace: str) -> tuple[str, str, str]:
    code = (marketplace or "US").upper()
    domain = MARKETPLACE_DOMAINS.get(code, MARKETPLACE_DOMAINS["US"])
    domain_suffix = domain.replace("www.amazon.", "").replace("amazon.", "")
    return code, domain, domain_suffix


def _country_code(marketplace: str) -> str:
    code = (marketplace or "US").upper()
    return {
        "US": "us",
        "UK": "gb",
        "GB": "gb",
        "CA": "ca",
        "DE": "de",
        "FR": "fr",
        "IT": "it",
        "ES": "es",
        "JP": "jp",
        "AU": "au",
        "MX": "mx",
        "NL": "nl",
        "SE": "se",
        "PL": "pl",
        "IN": "in",
        "AE": "ae",
        "BR": "br",
        "TR": "tr",
        "SA": "sa",
        "SG": "sg",
    }.get(code, "us")


def _price_to_number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value") or value.get("raw") or value.get("display") or value.get("name") or ""
    text = str(value or "")
    translated = re.search(r"(\d{1,4})\s*(?:美元|美金|USD|usd)\s*(\d{2})\b", text)
    if translated:
        return float(f"{translated.group(1)}.{translated.group(2)}")
    split_cents = re.search(r"\b(\d{1,4})\s+(\d{2})\b", text)
    if split_cents and any(token in text for token in ("$", "美元", "美金", "USD", "usd")):
        return float(f"{split_cents.group(1)}.{split_cents.group(2)}")
    match = re.search(r"[\d,.]+", text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _number(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("total") or value.get("value") or value.get("raw") or ""
    match = re.search(r"([\d,.]+)\s*([KkMm]?)", str(value or ""))
    if not match:
        return None
    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    suffix = match.group(2).lower()
    if suffix == "k":
        amount *= 1000
    elif suffix == "m":
        amount *= 1000000
    return int(amount)


def _review_count(*values: Any) -> int | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            nested = _review_count(
                value.get("total"),
                value.get("count"),
                value.get("ratings_count"),
                value.get("review_count"),
                value.get("value"),
                value.get("raw"),
                value.get("text"),
            )
            if nested is not None:
                return nested
            continue
        text = str(value or "").strip()
        if not text:
            continue
        lower = text.lower()
        if re.search(r"\bout\s+of\s+5\b", lower) or re.search(r"\bstars?\b", lower):
            if not re.search(r"\b(global\s+ratings?|ratings?|reviews?)\b", lower):
                continue
        explicit = re.search(r"([\d,.]+)\s*([KkMm]?)\s*(?:global\s+ratings?|ratings?|reviews?)\b", text, re.I)
        parsed = _number(explicit.group(0) if explicit else text)
        if parsed is not None:
            return parsed
    return None


def _rating(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("rating") or value.get("value") or value.get("raw") or ""
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _bsr_fields(value: Any) -> tuple[str, str]:
    if isinstance(value, list):
        for item in value:
            rank, category = _bsr_fields(item)
            if rank or category:
                return rank, category
        return "", ""
    if isinstance(value, dict):
        rank_value = (
            value.get("rank")
            or value.get("bsr_rank")
            or value.get("best_sellers_rank")
            or value.get("value")
            or value.get("raw")
            or value.get("text")
            or ""
        )
        category = _clean_text(str(value.get("category") or value.get("name") or value.get("department") or ""))
        if isinstance(rank_value, (dict, list)):
            nested_rank, nested_category = _bsr_fields(rank_value)
            return nested_rank, category or nested_category
        rank_number = _number(rank_value)
        return (str(rank_number) if rank_number else _clean_text(str(rank_value or "")), category)
    text = _clean_text(str(value or ""))
    if not text:
        return "", ""
    rank_number = _number(text)
    category_match = re.search(r"\bin\s+([^|,;]+)", text, re.I)
    category = _clean_text(category_match.group(1)) if category_match else ""
    return (str(rank_number) if rank_number else text, category)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text_from_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("raw", "display", "value", "name", "text"):
            if value.get(key):
                return str(value[key])
        return ""
    return str(value or "")


def _url_from_image(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("link", "url", "image", "image_url", "src", "data_src", "large", "large_url", "hiRes", "hi_res", "hires"):
            if value.get(key):
                return str(value.get(key))
        nested = value.get("images") or value.get("sources")
        if isinstance(nested, list) and nested:
            return _url_from_image(nested[-1])
        return ""
    return str(value or "")


def _clean_image_url(url: str) -> str:
    text = unquote(str(url or "")).replace("\\u0026", "&").strip()
    text = text.split(" ")[0].strip(" '\"")
    if text.startswith("//"):
        text = f"https:{text}"
    return text


def _dedupe_image_urls(values: list[Any], limit: int | None = None) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for item in values:
        url = _clean_image_url(_url_from_image(item))
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if limit and len(urls) >= limit:
            break
    return urls


def _collect_image_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            out.extend(_collect_image_values(item))
        return out
    if isinstance(value, dict):
        direct = _url_from_image(value)
        out = [direct] if direct else []
        for key in (
            "images",
            "image_urls",
            "aplus_image_urls",
            "a_plus_image_urls",
            "aplus_images",
            "a_plus_images",
            "modules",
            "content",
            "items",
            "sections",
        ):
            if key in value:
                out.extend(_collect_image_values(value.get(key)))
        return out
    return [value] if value else []


def _is_aplus_image_url(url: str) -> bool:
    lowered = url.lower()
    if "m.media-amazon.com/images" not in lowered:
        return False
    blocked = (
        "grey-pixel",
        "transparent-pixel",
        "loading",
        "sprite",
        "icon",
        "logo",
        "pagination",
        "play-button",
    )
    if any(token in lowered for token in blocked):
        return False
    return True


def _filter_aplus_image_urls(values: list[Any]) -> list[str]:
    cleaned = [url for url in _dedupe_image_urls(_collect_image_values(values)) if _is_aplus_image_url(url)]
    return cleaned[:9]


def _extract_aplus_from_html(html: str) -> tuple[list[str], str]:
    if not html:
        return [], ""
    soup = BeautifulSoup(html, "lxml")
    containers = []
    for selector in (
        "#aplus",
        "#aplus_feature_div",
        "#aplus3p_feature_div",
        "#dpx-aplus-product-description_feature_div",
        "[data-feature-name='aplus']",
    ):
        containers.extend(soup.select(selector))
    if not containers:
        containers.extend(soup.find_all(id=re.compile("aplus", re.I)))

    image_candidates: list[str] = []
    text_parts: list[str] = []
    for container in containers[:4]:
        text = _clean_text(container.get_text(" ", strip=True))
        if text:
            text_parts.append(text)
        for img in container.find_all("img"):
            candidates = [img.get("data-src"), img.get("data-a-hires"), img.get("src")]
            srcset = img.get("srcset") or img.get("data-srcset") or ""
            for part in str(srcset).split(","):
                candidates.append(part.strip().split(" ")[0])
            for candidate in candidates:
                url = _clean_image_url(str(candidate or ""))
                if url:
                    image_candidates.append(url)
    return _filter_aplus_image_urls(image_candidates), " ".join(text_parts)[:4000]


def _candidate_lists(value: Any) -> list[list[dict[str, Any]]]:
    lists: list[list[dict[str, Any]]] = []
    if isinstance(value, list):
        rows = [row for row in value if isinstance(row, dict)]
        if rows:
            lists.append(rows)
        return lists
    if not isinstance(value, dict):
        return lists
    for key in (
        "items",
        "results",
        "products",
        "organic_results",
        "organicResults",
        "search_results",
        "searchResults",
        "data",
    ):
        child = value.get(key)
        if child is value:
            continue
        lists.extend(_candidate_lists(child))
    return lists


def _ensure_scraperapi_provider() -> None:
    if AMAZON_CAPTURE_PROVIDER not in {"scraperapi", "scraper_api"}:
        raise ScrapelessCaptureError("ScraperAPI采集通道未配置")


async def _scraperapi_request(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    _ensure_scraperapi_provider()
    key = _api_key()
    if not key:
        raise ScrapelessCaptureError("ScraperAPI采集通道未配置")
    clean_params = {k: v for k, v in params.items() if v not in (None, "")}
    clean_params["api_key"] = key
    if SCRAPERAPI_ULTRA_PREMIUM:
        clean_params["ultra_premium"] = "true"
    elif SCRAPERAPI_PREMIUM:
        clean_params["premium"] = "true"
    url = f"{SCRAPERAPI_BASE_URL}/structured/amazon/{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=SCRAPERAPI_TIMEOUT_SECONDS, trust_env=False) as client:
            response = await client.get(url, params=clean_params)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:300] if exc.response is not None else ""
        logger.warning("ScraperAPI Amazon %s failed status=%s body=%s", endpoint, exc.response.status_code if exc.response else "", body)
        raise ScrapelessCaptureError("ScraperAPI采集失败") from exc
    except Exception as exc:
        logger.warning("ScraperAPI Amazon %s failed: %s", endpoint, exc)
        raise ScrapelessCaptureError("ScraperAPI采集失败") from exc


async def _scraperapi_html(url: str, marketplace: str) -> str:
    _ensure_scraperapi_provider()
    key = _api_key()
    if not key:
        raise ScrapelessCaptureError("ScraperAPI采集通道未配置")
    params: dict[str, Any] = {
        "api_key": key,
        "url": url,
        "country_code": _country_code(marketplace),
    }
    if SCRAPERAPI_ULTRA_PREMIUM:
        params["ultra_premium"] = "true"
    elif SCRAPERAPI_PREMIUM:
        params["premium"] = "true"
    try:
        async with httpx.AsyncClient(timeout=SCRAPERAPI_TIMEOUT_SECONDS, trust_env=False) as client:
            response = await client.get(f"{SCRAPERAPI_BASE_URL}/", params=params)
            response.raise_for_status()
            return response.text
    except Exception as exc:
        logger.warning("ScraperAPI HTML capture failed: %s", exc)
        return ""


def _parse_search_html(html: str, keyword: str, marketplace: str, batch_index: int) -> list[dict[str, Any]]:
    """Parse Amazon search results from raw HTML, extracting items from s-search-result cards."""
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select('[data-component-type="s-search-result"]')
    if not cards:
        cards = soup.select('.s-result-item[data-asin]')
    if not cards:
        return []

    marketplace_code, domain, _ = _marketplace_domain(marketplace)
    rank_start = (batch_index - 1) * 10 + 1
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for idx, card in enumerate(cards):
        if len(items) >= 10:
            break
        asin = (card.get("data-asin") or "").strip().upper()
        if not asin or not re.fullmatch(r"[A-Z0-9]{10}", asin):
            continue
        if asin in seen:
            continue
        seen.add(asin)

        # Title
        title_el = card.select_one("h2 a span") or card.select_one("h2 span") or card.select_one(".a-text-normal")
        title = _clean_text(title_el.get_text() if title_el else "")

        # Price
        price_whole = card.select_one(".a-price-whole")
        price_fraction = card.select_one(".a-price-fraction")
        price_symbol = card.select_one(".a-price-symbol")
        price = None
        price_text = ""
        if price_whole:
            price_text = (price_symbol.get_text(strip=True) if price_symbol else "$") + price_whole.get_text(strip=True)
            if price_fraction:
                price_text += price_fraction.get_text(strip=True)
            price = _price_to_number(price_text)

        # Rating
        rating_el = card.select_one(".a-icon-alt") or card.select_one("[aria-label*='out of']")
        rating_text = _clean_text(rating_el.get_text() if rating_el else "")
        rating_match = re.search(r"([\d.]+)", rating_text) if rating_text else None
        rating = float(rating_match.group(1)) if rating_match else None

        # Review count
        review_count = None
        review_el = card.select_one("[aria-label*='ratings']") or card.select_one(".a-size-base.s-underline-text")
        if review_el:
            review_text = _clean_text(review_el.get_text() or review_el.get("aria-label", ""))
            rc_match = re.search(r"([\d,]+)", review_text)
            if rc_match:
                review_count = int(rc_match.group(1).replace(",", ""))

        # URL
        url = ""
        for a_el in card.select("a"):
            href = (a_el.get("href") or "").strip()
            if f"/dp/{asin}" in href:
                url = f"https://{domain}{href}" if href.startswith("/") else href
                url = url.split("/ref=")[0]
                break
        if not url:
            url = f"https://{domain}/dp/{asin}"

        # Sponsored
        is_sponsored = bool(card.select_one(".s-sponsored-label-text"))
        if not is_sponsored:
            card_text = card.get_text(" ", strip=True)
            is_sponsored = "Sponsored" in card_text

        rank = rank_start + idx
        items.append({
            "searchRank": int(rank),
            "asin": asin,
            "url": url,
            "title": title,
            "price": price,
            "priceText": price_text,
            "searchPrice": price,
            "searchPriceText": price_text,
            "detailPrice": None,
            "detailPriceText": "",
            "priceSource": "search_html" if price_text else "missing",
            "priceStatus": "search_price" if price_text else "missing",
            "rating": rating,
            "reviewCount": review_count,
            "imageUrl": "",
            "isSponsored": is_sponsored,
            "source": "scraperapi_search_html_fallback",
            "status": "search_snapshot",
            "error": "",
            "captureDepth": "search_result",
            "keyword": keyword,
            "marketplace": marketplace,
        })

    page_items = items[:10]
    for index, item in enumerate(page_items, start=rank_start):
        item["searchRank"] = index
    return page_items


async def _search_html_fallback(keyword: str, domain: str, marketplace: str, batch_index: int) -> dict[str, Any]:
    """Fetch Amazon search page HTML via ScraperAPI generic endpoint and parse locally."""
    html = await _scraperapi_html(f"https://{domain}/s?k={keyword}&page={batch_index}", marketplace)
    if not html:
        raise ScrapelessCaptureError("ScraperAPI搜索HTML获取失败")
    items = _parse_search_html(html, keyword, marketplace, batch_index)
    if not items:
        raise ScrapelessCaptureError("搜索HTML解析无结果")
    return {
        "items": items,
    }


async def _search_raw(keyword: str, domain: str, domain_suffix: str, batch_index: int, marketplace: str = "US") -> dict[str, Any]:
    """Try ScraperAPI structured search endpoint, fall back to HTML parsing on failure."""
    try:
        result = await _scraperapi_request(
            "search",
            {
                "query": keyword,
                "tld": domain_suffix,
                "page": batch_index,
            },
        )
        # Check if structured endpoint returned empty results
        rows = _candidate_lists(result)
        if not any(len(r) > 0 for r in rows):
            logger.info("ScraperAPI search returned empty, falling back to HTML")
            return await _search_html_fallback(keyword, domain, marketplace, batch_index)
        return result
    except ScrapelessCaptureError:
        logger.info("ScraperAPI search structured endpoint failed, falling back to HTML")
        return await _search_html_fallback(keyword, domain, marketplace, batch_index)


async def _product_raw(asin: str, domain: str, domain_suffix: str) -> dict[str, Any]:
    return await _scraperapi_request(
        "product",
        {
            "asin": asin,
            "tld": domain_suffix,
        },
    )


def _normalize_search_items(raw: dict[str, Any], keyword: str, marketplace: str, batch_index: int) -> list[dict[str, Any]]:
    marketplace, domain, _ = _marketplace_domain(marketplace)
    rank_start = (batch_index - 1) * 10 + 1
    rows: list[dict[str, Any]] = []
    for candidate in _candidate_lists(raw):
        if len(candidate) > len(rows):
            rows = candidate
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for offset, row in enumerate(rows):
        row = _as_dict(row)
        title = _clean_text(str(row.get("title") or row.get("name") or row.get("product_title") or ""))
        if not title:
            continue
        asin = str(row.get("asin") or row.get("ASIN") or row.get("product_asin") or "").strip().upper()
        url = str(row.get("url") or row.get("link") or row.get("product_url") or "").strip()
        if not asin and url:
            url_for_match = unquote(url).upper()
            match = re.search(r"/(?:DP|GP/PRODUCT)/([A-Z0-9]{10})", url_for_match) or re.search(
                r"(?:[?&]|%26)(?:ASIN|BWASIN|PD_RD_I)=([A-Z0-9]{10})",
                url_for_match,
            )
            asin = match.group(1) if match else ""
        if asin and not re.fullmatch(r"[A-Z0-9]{10}", asin):
            asin = ""
        key = asin or title.lower()
        if key in seen:
            continue
        seen.add(key)
        if url.startswith("/"):
            url = f"https://{domain}{url}"
        elif not url and asin:
            url = f"https://{domain}/dp/{asin}"
        rank = _number(row.get("searchRank") or row.get("rank") or row.get("position")) or (rank_start + offset)
        price_text = _clean_text(_text_from_value(row.get("priceText") or row.get("price_text") or row.get("price_string") or row.get("price") or ""))
        price = _price_to_number(row.get("price") or price_text)
        review_count = _review_count(
            row.get("reviewCount"),
            row.get("review_count"),
            row.get("total_reviews"),
            row.get("ratings_total"),
            row.get("ratingsTotal"),
            row.get("total_ratings"),
            row.get("ratings"),
            row.get("reviews"),
        )
        normalized.append(
            {
                "searchRank": int(rank),
                "asin": asin,
                "url": url,
                "title": title,
                "price": price,
                "priceText": price_text,
                "searchPrice": price,
                "searchPriceText": price_text,
                "detailPrice": None,
                "detailPriceText": "",
                "priceSource": "search_result" if price_text else "missing",
                "priceStatus": "search_price" if price_text else "missing",
                "rating": _rating(row.get("rating") or row.get("stars")),
                "reviewCount": review_count,
                "imageUrl": _url_from_image(row.get("imageUrl") or row.get("image_url") or row.get("thumbnail") or row.get("image")),
                "isSponsored": bool(row.get("isSponsored") or row.get("sponsored") or row.get("ad")),
                "source": "scraperapi_amazon_search",
                "status": "search_snapshot",
                "error": "",
                "captureDepth": "search_result",
                "keyword": keyword,
                "marketplace": marketplace,
            }
        )
        if len(normalized) >= rank_start + 9:
            break
    page_items = normalized[rank_start - 1 : rank_start + 9]
    for index, item in enumerate(page_items, start=rank_start):
        item["searchRank"] = index
    return page_items


def _search_quality(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    with_asin = len([item for item in items if str(item.get("asin") or "").strip()])
    with_title = len([item for item in items if str(item.get("title") or "").strip()])
    with_price = len([item for item in items if _price_to_number(item.get("price") or item.get("priceText"))])
    with_reviews = len([item for item in items if _review_count(item.get("reviewCount"), item.get("reviews")) is not None])
    with_image = len([item for item in items if str(item.get("imageUrl") or "").strip()])
    return {
        "total": total,
        "with_asin": with_asin,
        "with_title": with_title,
        "with_price": with_price,
        "with_reviews": with_reviews,
        "with_image": with_image,
        "required_ok": total >= 10 and with_asin >= 10 and with_title >= 10,
    }


async def capture_top40_batch_via_scrapeless(
    keyword: str,
    marketplace: str = "US",
    batch_index: int = 1,
    include_details: bool = False,
) -> dict[str, Any]:
    marketplace, domain, domain_suffix = _marketplace_domain(marketplace)
    rank_start = (batch_index - 1) * 10 + 1
    raw = await _search_raw(keyword, domain, domain_suffix, batch_index, marketplace)
    items = _normalize_search_items(raw, keyword, marketplace, batch_index)
    quality = _search_quality(items)
    return {
        "marketplace": marketplace,
        "keyword": keyword,
        "batchIndex": batch_index,
        "rankRange": [rank_start, rank_start + 9],
        "status": "ok" if quality["required_ok"] else "partial",
        "items": items,
        "errors": [] if quality["required_ok"] else ["搜索样本字段不完整"],
        "quality": quality,
        "dataSource": "scraperapi_amazon_search",
        "captureDepth": "search_result",
        "includeDetails": include_details,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "raw": raw if os.getenv("SCRAPELESS_DEBUG_RAW", "").lower() == "true" else None,
    }


def _normalize_product(raw: dict[str, Any], asin: str, marketplace: str) -> dict[str, Any]:
    data = _as_dict(raw.get("data")) or raw
    for key in ("product", "result", "item", "request_info"):
        if isinstance(data.get(key), dict):
            data = data[key]
            break
    title = _clean_text(str(data.get("title") or data.get("name") or data.get("product_title") or ""))
    bullets = data.get("bullet_points") or data.get("bullets") or data.get("feature_bullets") or data.get("features") or []
    if isinstance(bullets, str):
        bullets = [line.strip() for line in re.split(r"[\n;]+", bullets) if line.strip()]
    images = data.get("high_res_images") or data.get("image_urls") or data.get("images") or data.get("imageUrl") or data.get("image_url") or []
    if isinstance(images, str):
        images = [images]
    aplus_images = (
        data.get("aplus_image_urls")
        or data.get("a_plus_image_urls")
        or data.get("aplus_images")
        or data.get("a_plus_images")
        or data.get("aPlusImages")
        or data.get("a_plus")
        or data.get("aplus")
        or []
    )
    if isinstance(aplus_images, str):
        aplus_images = [aplus_images]
    aplus_content = data.get("aplus_content") or data.get("a_plus_content") or data.get("aPlusContent") or data.get("product_description") or data.get("description") or ""
    price_text = _clean_text(_text_from_value(data.get("priceText") or data.get("price_text") or data.get("pricing") or data.get("price") or ""))
    product_info = _as_dict(data.get("product_information"))
    customer_reviews = _as_dict(product_info.get("customer_reviews"))
    image_urls = _dedupe_image_urls(_as_list(images), 9)
    aplus_image_urls = _filter_aplus_image_urls(_as_list(aplus_images))
    bsr_rank, bsr_category = _bsr_fields(
        data.get("bsr")
        or data.get("bsr_rank")
        or data.get("best_sellers_rank")
        or data.get("sales_rank")
        or product_info.get("best_sellers_rank")
    )
    return {
        "scrape_success": bool(title or bullets or images),
        "data_source": "scraperapi_amazon_product",
        "asin": str(data.get("asin") or asin).strip().upper(),
        "marketplace": marketplace,
        "title": title,
        "brand": _clean_text(str(data.get("brand") or "")),
        "price": _price_to_number(data.get("pricing") or data.get("price") or price_text),
        "price_text": price_text,
        "rating": _rating(data.get("average_rating") or data.get("rating") or data.get("stars") or customer_reviews.get("stars")),
        "review_count": _review_count(
            data.get("total_reviews"),
            data.get("total_ratings"),
            data.get("ratings_total"),
            customer_reviews.get("ratings_count"),
            customer_reviews.get("total_ratings"),
            customer_reviews.get("reviews_count"),
            data.get("review_count"),
            data.get("reviewCount"),
            data.get("ratings"),
            data.get("reviews"),
        ),
        "bullet_points": [_clean_text(str(item)) for item in _as_list(bullets) if _clean_text(str(item))],
        "image_urls": image_urls,
        "image_count": len(image_urls),
        "aplus_content": aplus_content if isinstance(aplus_content, (str, list, dict)) else "",
        "aplus_image_urls": aplus_image_urls,
        "aplus_image_count": len(aplus_image_urls),
        "has_a_plus": bool(aplus_content or aplus_image_urls),
        "category": _clean_text(str(data.get("product_category") or data.get("category") or data.get("category_path") or "")),
        "bsr_rank": bsr_rank,
        "bsr_category": bsr_category,
        "bsr": data.get("bsr") or data.get("best_sellers_rank") or product_info.get("best_sellers_rank"),
        "low_star_reviews": data.get("low_star_reviews") or data.get("reviews_low") or [],
    }


async def scrape_amazon_product_via_scrapeless(asin: str, marketplace: str = "US") -> dict[str, Any]:
    asin = str(asin or "").strip().upper()
    marketplace, domain, domain_suffix = _marketplace_domain(marketplace)
    raw = await _product_raw(asin, domain, domain_suffix)
    parsed = _normalize_product(raw, asin, marketplace)
    needs_html_fallback = parsed.get("scrape_success") and (
        not parsed.get("price")
        or not parsed.get("bsr_rank")
        or not parsed.get("aplus_image_urls")
    )
    if needs_html_fallback:
        html = await _scraperapi_html(f"https://{domain}/dp/{asin}", marketplace)
        html_product = _parse_product_page(html, marketplace) or {}
        for key in ("price", "rating", "review_count", "bsr_rank", "bsr_category", "category", "brand"):
            if not parsed.get(key) and html_product.get(key):
                parsed[key] = html_product.get(key)
        if not parsed.get("image_urls") and html_product.get("image_urls"):
            parsed["image_urls"] = html_product.get("image_urls") or []
            parsed["image_count"] = len(parsed["image_urls"])
        if html_product.get("has_a_plus"):
            parsed["has_a_plus"] = True
        if not parsed.get("aplus_image_urls") and html_product.get("aplus_image_urls"):
            parsed["aplus_image_urls"] = html_product.get("aplus_image_urls") or []
            parsed["aplus_image_count"] = len(parsed["aplus_image_urls"])
            parsed["has_a_plus"] = True
        if not parsed.get("aplus_content") and html_product.get("aplus_content"):
            parsed["aplus_content"] = html_product.get("aplus_content") or ""
            parsed["has_a_plus"] = True
        aplus_urls, aplus_text = _extract_aplus_from_html(html)
        if aplus_urls:
            parsed["aplus_image_urls"] = aplus_urls
            parsed["aplus_image_count"] = len(aplus_urls)
            parsed["has_a_plus"] = True
        if aplus_text and not parsed.get("aplus_content"):
            parsed["aplus_content"] = aplus_text
            parsed["has_a_plus"] = True
    if not parsed.get("scrape_success"):
        raise ScrapelessCaptureError("未获取到商品页面数据")
    if os.getenv("SCRAPERAPI_DEBUG_RAW", "").lower() == "true":
        parsed["_raw_capture"] = raw
    return parsed
