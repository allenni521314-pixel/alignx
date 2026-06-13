import asyncio
import base64
import json
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx
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
_CURL_CFFI_DISABLED = False

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
    match = re.search(r"([\d,.]+)\s*([KkMm]?)", text or "")
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
        suffix = match.group(2).lower()
        if suffix == "k":
            value *= 1000
        elif suffix == "m":
            value *= 1000000
        return int(value)
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
    review_el = (
        card.select_one("a[href*='customerReviews'] span.a-size-base")
        or card.select_one("a[aria-label*='ratings']")
        or card.select_one("a[aria-label*='rating']")
        or card.select_one("span[aria-label*='ratings']")
    )
    price_el = card.select_one(".a-price .a-offscreen")
    sponsored_blob = _clean_text(card.get_text(" ", strip=True)).lower()

    href = link_el.get("href") if link_el else f"/dp/{asin}"
    url = href if href.startswith("http") else f"https://{domain}{href}"
    url = url.split("/ref=")[0] if "/ref=" in url else url

    price_text = _clean_text(price_el.get_text(" ", strip=True)) if price_el else ""
    rating_text = _clean_text(rating_el.get_text(" ", strip=True)) if rating_el else ""
    review_text = _clean_text((review_el.get("aria-label") or review_el.get_text(" ", strip=True)) if review_el else "")

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
    is_search_page = "/s?" in url

    lang = ACCEPT_LANG.get(marketplace, "en-US,en;q=0.9")
    headers = _build_desktop_headers(lang)
    if referer:
        headers["Referer"] = referer

    if is_search_page:
        try:
            async with httpx.AsyncClient(timeout=18, follow_redirects=True, trust_env=False) as client:
                response = await client.get(url, headers=headers)
            return int(response.status_code or 0), response.text or ""
        except BaseException as exc:
            logger.info("Safe search fetch failed for %s: %s", url, exc)
            return 0, ""

    try:
        from scrapling.fetchers import AsyncFetcher
    except ImportError as exc:
        raise RuntimeError("Scrapling is not installed in the backend environment") from exc

    response = await AsyncFetcher.get(
        url,
        headers=headers,
        timeout=18,
        retries=0,
        follow_redirects=True,
        stealthy_headers=True,
    )
    html = getattr(response, "html_content", None) or getattr(response, "body", b"")
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="ignore")
    status = int(getattr(response, "status", 0) or 0)
    text = str(html or "")
    if status >= 400 or (is_search_page and ("data-asin" not in text or "bm-verify" in text)):
        fallback_status, fallback_html = await _fetch_html_curl_cffi(url, marketplace, referer=referer)
        if fallback_status and fallback_html and (not is_search_page or "data-asin" in fallback_html):
            return fallback_status, fallback_html
    return status, text


async def _fetch_html_curl_cffi(url: str, marketplace: str, referer: str = "") -> tuple[int, str]:
    global _CURL_CFFI_DISABLED
    if _CURL_CFFI_DISABLED:
        return 0, ""
    try:
        from curl_cffi.requests import AsyncSession
    except ImportError:
        return 0, ""

    lang = ACCEPT_LANG.get(marketplace, "en-US,en;q=0.9")
    headers = _build_desktop_headers(lang)
    headers["Cookie"] = "lc-main=en_US; i18n-prefs=USD"
    if referer:
        headers["Referer"] = referer
    last_status = 0
    last_html = ""
    for attempt in range(1):
        try:
            async with AsyncSession(impersonate=random.choice(["chrome131", "chrome124", "chrome120", "chrome"])) as session:
                domain_match = re.search(r"https://([^/]+)/", url)
                if domain_match:
                    try:
                        await session.get(f"https://{domain_match.group(1)}/", headers=headers, timeout=8)
                        await asyncio.sleep(random.uniform(0.4, 1.1))
                    except Exception:
                        pass
                response = await session.get(url, headers=headers, timeout=18)
                last_status = int(response.status_code or 0)
                last_html = str(response.text or "")
                if "data-asin" in last_html or "/s?" not in url:
                    return last_status, last_html
                await asyncio.sleep(random.uniform(0.8, 1.6))
        except Exception as exc:
            logger.info("curl-cffi search fallback attempt %s failed for %s: %s", attempt + 1, url, exc)
            if "TLS connect error" in str(exc) or "OPENSSL_internal" in str(exc):
                _CURL_CFFI_DISABLED = True
                break
    return last_status, last_html


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


def _json_from_text(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text or "{}")
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    start = (text or "").find("{")
    end = (text or "").rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


async def _vision_extract_search_items(
    search_url: str,
    keyword: str,
    marketplace: str,
    domain: str,
    start_rank: int,
) -> list[dict[str, Any]]:
    try:
        from playwright.async_api import async_playwright
        from schemas.aihub import ChatMessage, ContentPartImage, ContentPartText, GenTxtRequest, ImageUrl
        from services.aihub import AIHubService
    except Exception as exc:
        logger.info("Local browser vision fallback unavailable: %s", exc)
        return []

    lang = ACCEPT_LANG.get(marketplace, "en-US,en;q=0.9")
    ua = random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    ])
    async def _capture_browser_data() -> tuple[bytes, list[dict[str, Any]]]:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
            chrome_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            if chrome_path.exists():
                browser = await p.chromium.launch(executable_path=str(chrome_path), headless=True, args=launch_args)
            else:
                try:
                    browser = await p.chromium.launch(channel="chrome", headless=True, args=launch_args)
                except Exception:
                    browser = await p.chromium.launch(headless=True, args=launch_args)
            context = await browser.new_context(
                user_agent=ua,
                locale=lang.split(",")[0].split(";")[0],
                viewport={"width": 1440, "height": 1800},
                java_script_enabled=True,
            )
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """)
            page = await context.new_page()
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(3500)
                try:
                    cards = page.locator("div[data-component-type='s-search-result']")
                    if await cards.count() > 0:
                        await cards.first.scroll_into_view_if_needed(timeout=5000)
                    else:
                        await page.mouse.wheel(0, 520)
                    await page.wait_for_timeout(800)
                except Exception:
                    pass
                dom_items: list[dict[str, Any]] = []
                try:
                    raw_items = await page.eval_on_selector_all(
                        "div[data-component-type='s-search-result'][data-asin]",
                        """
                        (cards) => cards.slice(0, 12).map((card) => {
                          const text = (el) => el ? (el.textContent || '').replace(/\\s+/g, ' ').trim() : '';
                          const attr = (el, name) => el ? (el.getAttribute(name) || '') : '';
                          const asin = (card.getAttribute('data-asin') || '').trim().toUpperCase();
                          const titleEl = card.querySelector('h2 span') || card.querySelector('h2 a') || card.querySelector("[data-cy='title-recipe'] span");
                          const linkEl = card.querySelector('h2 a[href]') || card.querySelector('a.a-link-normal.s-no-outline[href]');
                          const imageEl = card.querySelector('img.s-image');
                          const priceEl = card.querySelector('.a-price .a-offscreen');
                          const ratingEl = card.querySelector('span.a-icon-alt');
                          const reviewEl =
                            card.querySelector("a[href*='customerReviews'] span.a-size-base") ||
                            card.querySelector("a[aria-label*='ratings']") ||
                            card.querySelector("a[aria-label*='rating']") ||
                            card.querySelector("span[aria-label*='ratings']");
                          return {
                            asin,
                            title: text(titleEl),
                            href: attr(linkEl, 'href'),
                            imageUrl: attr(imageEl, 'src'),
                            priceText: text(priceEl),
                            ratingText: text(ratingEl),
                            reviewText: attr(reviewEl, 'aria-label') || text(reviewEl),
                            isSponsored: /sponsored|赞助/i.test(text(card)),
                          };
                        }).filter((row) => row.asin || row.title)
                        """,
                    )
                    if isinstance(raw_items, list):
                        rank = start_rank
                        for row in raw_items:
                            if not isinstance(row, dict):
                                continue
                            title = _clean_text(str(row.get("title") or ""))
                            asin = _clean_text(str(row.get("asin") or "")).upper()
                            if not title or not re.fullmatch(r"[A-Z0-9]{10}", asin):
                                continue
                            href = str(row.get("href") or f"/dp/{asin}")
                            url = href if href.startswith("http") else f"https://{domain}{href}"
                            url = url.split("/ref=")[0] if "/ref=" in url else url
                            price_text = _clean_text(str(row.get("priceText") or ""))
                            review_text = _clean_text(str(row.get("reviewText") or ""))
                            dom_items.append(
                                {
                                    "searchRank": rank,
                                    "asin": asin,
                                    "sourceId": f"local_browser_dom:{keyword}:{rank}:{asin}",
                                    "url": url,
                                    "title": title,
                                    "price": _price_to_number(price_text),
                                    "priceText": price_text,
                                    "searchPrice": _price_to_number(price_text),
                                    "searchPriceText": price_text,
                                    "detailPrice": None,
                                    "detailPriceText": "",
                                    "priceSource": "local_browser_dom" if price_text else "missing",
                                    "priceStatus": "dom_price" if price_text else "missing",
                                    "rating": _rating_number(str(row.get("ratingText") or "")),
                                    "reviewCount": _text_number(review_text),
                                    "imageUrl": str(row.get("imageUrl") or ""),
                                    "isSponsored": bool(row.get("isSponsored")),
                                    "source": "local_browser_dom",
                                }
                            )
                            rank += 1
                except Exception as exc:
                    logger.info("Local browser DOM extraction failed for %s: %s", search_url, exc)
                screenshot = await page.screenshot(full_page=False, type="png")
                return screenshot, dom_items
            finally:
                await browser.close()

    try:
        screenshot, dom_items = await asyncio.wait_for(_capture_browser_data(), timeout=45)
    except Exception as exc:
        logger.info("Local browser screenshot failed for %s: %s", search_url, exc)
        return []
    if dom_items:
        logger.info("Local browser DOM extracted %s items for %s", len(dom_items), keyword)
        return dom_items

    image_data = f"data:image/png;base64,{base64.b64encode(screenshot).decode('ascii')}"
    prompt = {
        "task": "Extract visible Amazon search result products from screenshot.",
        "keyword": keyword,
        "marketplace": marketplace,
        "rules": [
            "Only extract products visibly shown in the screenshot.",
            "Do not invent products or missing fields.",
            "If ASIN is not visible, leave asin empty.",
            "Return JSON only.",
        ],
        "schema": {
            "items": [
                {
                    "title": "visible product title",
                    "priceText": "visible price",
                    "rating": 4.3,
                    "reviewText": "visible review count",
                    "isSponsored": True,
                }
            ]
        },
    }
    try:
        service = AIHubService()
        response = await service.gentxt(
            GenTxtRequest(
                messages=[
                    ChatMessage(role="system", content="你只做Amazon搜索页截图OCR和结构化抽取。只返回JSON，不输出Markdown。"),
                    ChatMessage(
                        role="user",
                        content=[
                            ContentPartText(type="text", text=json.dumps(prompt, ensure_ascii=False)),
                            ContentPartImage(type="image_url", image_url=ImageUrl(url=image_data)),
                        ],
                    ),
                ],
                model="AI_VISION_MODEL",
                temperature=0,
                max_tokens=3000,
            )
        )
        data = _json_from_text(response.content or "") or {}
        raw_items = data.get("items") or []
        if not isinstance(raw_items, list):
            return []
        items: list[dict[str, Any]] = []
        rank = start_rank
        for row in raw_items[:10]:
            if not isinstance(row, dict):
                continue
            title = _clean_text(str(row.get("title") or ""))
            if len(title) < 8:
                continue
            asin = _clean_text(str(row.get("asin") or "")).upper()
            if not re.fullmatch(r"[A-Z0-9]{10}", asin):
                asin = ""
            price_text = _clean_text(str(row.get("priceText") or row.get("price") or ""))
            review_text = _clean_text(str(row.get("reviewText") or row.get("reviews") or row.get("reviewCount") or ""))
            items.append(
                {
                    "searchRank": rank,
                    "asin": asin,
                    "sourceId": f"local_browser_vision:{keyword}:{rank}",
                    "url": f"https://{domain}/s?k={quote_plus(keyword)}",
                    "title": title,
                    "price": _price_to_number(price_text),
                    "priceText": price_text,
                    "searchPrice": _price_to_number(price_text),
                    "searchPriceText": price_text,
                    "detailPrice": None,
                    "detailPriceText": "",
                    "priceSource": "local_browser_vision" if price_text else "missing",
                    "priceStatus": "vision_price" if price_text else "missing",
                    "rating": _rating_number(str(row.get("rating") or row.get("ratingText") or "")),
                    "reviewCount": _text_number(review_text),
                    "imageUrl": "",
                    "isSponsored": bool(row.get("isSponsored")),
                    "source": "local_browser_vision",
                }
            )
            rank += 1
        if items:
            logger.info("Local browser vision extracted %s items for %s", len(items), keyword)
        return items
    except Exception as exc:
        logger.info("Vision extraction failed for %s: %s", search_url, exc)
        return []


async def _fetch_search_snapshot(keyword: str, marketplace: str, limit: int) -> tuple[str, list[dict[str, Any]], list[str]]:
    marketplace, domain = _marketplace_url(marketplace)
    errors: list[str] = []
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    max_pages = min(4, max(1, (limit + 9) // 10))
    for page in range(1, max_pages + 1):
        search_url = f"https://{domain}/s?k={quote_plus(keyword)}&page={page}"
        parsed_items: list[dict[str, Any]] = []
        try:
            status, html = await _fetch_html(search_url, marketplace)
        except BaseException as exc:
            errors.append(f"search_page_{page}: {exc}")
            vision_items = await _vision_extract_search_items(search_url, keyword, marketplace, domain, len(items) + 1)
            if vision_items:
                parsed_items = vision_items
                status = 200
                html = ""
                errors.append(f"search_page_{page}: local_browser_vision_fallback")
            else:
                break

        if not parsed_items and status and status < 400 and not _is_captcha_page(html):
            parsed_items = _parse_search_results(html, domain, len(items) + 1)
        if not parsed_items:
            vision_items = await _vision_extract_search_items(search_url, keyword, marketplace, domain, len(items) + 1)
            if vision_items:
                parsed_items = vision_items
                errors.append(f"search_page_{page}: local_browser_vision_fallback")
        if status >= 400 and not parsed_items:
            errors.append(f"search_page_{page}: http_{status}")
            break
        if _is_captcha_page(html) and not parsed_items:
            return "blocked", items, errors + [f"search_page_{page}: captcha_or_robot_check"]

        for item in parsed_items:
            item_key = str(item.get("asin") or item.get("sourceId") or f"{keyword}:{page}:{item.get('searchRank')}")
            if item_key in seen:
                continue
            seen.add(item_key)
            items.append(item)
            if len(items) >= limit:
                return "ok", items, errors

        if page < max_pages:
            await asyncio.sleep(random.uniform(2.0, 4.0))

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


async def capture_top40_batch(keyword: str, marketplace: str = "US", batch_index: int = 1, include_details: bool = False) -> dict[str, Any]:
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

    blocked = snapshot_status == "blocked"
    if include_details:
        captured: list[dict[str, Any]] = []
        for index, item in enumerate(batch_items, start=1):
            enriched = await _enrich_detail(item, marketplace)
            captured.append(enriched)
            if enriched.get("status") == "blocked":
                blocked = True
                errors.append(f"detail_{item['asin']}: captcha_or_robot_check")
                break
            if index < len(batch_items):
                await asyncio.sleep(random.uniform(1.5, 3.5))
    else:
        captured = [
            {
                **item,
                "status": "search_snapshot",
                "error": "",
                "captureDepth": "search_result",
            }
            for item in batch_items
        ]

    ok_count = sum(1 for item in captured if item.get("status") in {"ok", "search_snapshot"})
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
        "captureDepth": "detail_page" if include_details else "search_result",
        "analysisNote": (
            "Search snapshot saved first for public stability; detail-page enrichment can run later."
            if not include_details
            else "Raw capture only. Cleaning, normalization, and market opportunity analysis must run in the backend AI layer."
        ),
    }
