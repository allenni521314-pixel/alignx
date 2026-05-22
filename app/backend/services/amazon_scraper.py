"""
Amazon product page scraper with multi-strategy anti-detection.

Strategy order:
1. curl-cffi with Chrome TLS impersonation (fastest, bypasses TLS fingerprinting)
   - Attempt A: Desktop Chrome UA
   - Attempt B: Mobile Chrome UA (Amazon mobile pages are simpler, less blocking)
2. httpx with realistic headers (lightweight, no extra deps)
3. Playwright headless browser (renders full page like real browser) - optional
4. Returns failure → caller falls back to AI

Dependencies:
  Required: curl-cffi, beautifulsoup4, lxml, httpx
  Optional: playwright (for browser strategy)
"""

import asyncio
import json
import logging
import random
import re
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Marketplace domain mapping
MARKETPLACE_DOMAINS = {
    "US": "www.amazon.com",
    "UK": "www.amazon.co.uk",
    "DE": "www.amazon.de",
    "JP": "www.amazon.co.jp",
    "CA": "www.amazon.ca",
    "FR": "www.amazon.fr",
    "IT": "www.amazon.it",
    "ES": "www.amazon.es",
    "AU": "www.amazon.com.au",
    "IN": "www.amazon.in",
    "MX": "www.amazon.com.mx",
}

# Accept-Language by marketplace
ACCEPT_LANG = {
    "US": "en-US,en;q=0.9",
    "UK": "en-GB,en;q=0.9",
    "DE": "de-DE,de;q=0.9,en;q=0.8",
    "JP": "ja-JP,ja;q=0.9,en;q=0.8",
    "CA": "en-CA,en;q=0.9",
    "FR": "fr-FR,fr;q=0.9,en;q=0.8",
    "IT": "it-IT,it;q=0.9,en;q=0.8",
    "ES": "es-ES,es;q=0.9,en;q=0.8",
    "AU": "en-AU,en;q=0.9",
    "IN": "en-IN,en;q=0.9",
    "MX": "es-MX,es;q=0.9,en;q=0.8",
}

MARKETPLACE_CURRENCIES = {
    "US": ("$", "USD"),
    "UK": ("£", "GBP"),
    "DE": ("€", "EUR"),
    "FR": ("€", "EUR"),
    "IT": ("€", "EUR"),
    "ES": ("€", "EUR"),
    "JP": ("¥", "JPY"),
    "CA": ("$", "CAD"),
    "AU": ("$", "AUD"),
    "IN": ("₹", "INR"),
    "MX": ("$", "MXN"),
}

# Realistic desktop Chrome User-Agents (rotated)
_DESKTOP_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]

# Mobile User-Agents (Amazon mobile pages are simpler and less aggressively blocked)
_MOBILE_UAS = [
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0.6778.73 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
]


# ------------------------------------------------------------------ #
#  HTML Parsing Helpers                                                #
# ------------------------------------------------------------------ #

def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _extract_title(soup: BeautifulSoup) -> str:
    for sel in ["#productTitle", "#title_feature_div #title", "h1#title", "span#productTitle"]:
        el = soup.select_one(sel)
        if el:
            t = _clean_text(el.get_text())
            if len(t) > 5:
                return t
    return ""


def _parse_price_text(text: str, marketplace: str = "US") -> str:
    text = _clean_text(text)
    if not text:
        return ""
    lowered = text.lower()
    if any(token in lowered for token in ["list price", "was:", "save ", "/2 weeks", "/ 2 weeks", "per month", "select from", "payment plan", "monthly payment"]):
        return ""
    symbol, code = MARKETPLACE_CURRENCIES.get(marketplace, ("$", "USD"))
    if marketplace == "US" and "$" not in text and "USD" not in text.upper():
        return ""
    if marketplace in {"UK", "DE", "FR", "IT", "ES", "JP", "IN"} and symbol not in text and code not in text.upper():
        return ""
    # Avoid picking rating percentages, coupon amounts, or unrelated range text.
    match = re.search(r"(?:[$€£¥₹]\s*|USD\s*)?(\d{1,4}(?:[,.]\d{2})?)", text, flags=re.I)
    if not match:
        return ""
    price = match.group(1).replace(",", ".")
    try:
        value = float(price)
    except ValueError:
        return ""
    if value <= 0 or value > 9999:
        return ""
    return f"{value:.2f}".rstrip("0").rstrip(".") if "." in f"{value:.2f}" else str(value)


def _extract_price(soup: BeautifulSoup, marketplace: str = "US") -> str:
    """Extract the PDP buy-box/core price only, avoiding unrelated offer widgets."""
    primary_selectors = [
        "#corePriceDisplay_desktop_feature_div .priceToPay .a-offscreen",
        "#corePrice_feature_div .priceToPay .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .apexPriceToPay .a-offscreen",
        "#corePrice_feature_div .apexPriceToPay .a-offscreen",
        "#corePriceDisplay_desktop_feature_div [data-a-color='price'] .a-offscreen",
        "#corePrice_feature_div [data-a-color='price'] .a-offscreen",
    ]
    for sel in primary_selectors:
        el = soup.select_one(sel)
        if el:
            price = _parse_price_text(el.get_text(" ", strip=True), marketplace)
            if price:
                return price

    core_blocks = [
        "#corePriceDisplay_desktop_feature_div",
        "#corePrice_feature_div",
        "#apex_desktop",
        "#centerCol",
        "#buybox",
    ]
    for block_sel in core_blocks:
        block = soup.select_one(block_sel)
        if not block:
            continue
        for el in block.select(".a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice, #priceblock_saleprice, #price_inside_buybox"):
            context = _clean_text(el.parent.get_text(" ", strip=True) if el.parent else el.get_text(" ", strip=True))
            price = _parse_price_text(context, marketplace)
            if price:
                return price
        for price_el in block.select(".a-price"):
            offscreen = price_el.select_one(".a-offscreen")
            if offscreen:
                price = _parse_price_text(offscreen.get_text(), marketplace)
                if price:
                    return price
            whole = _clean_text(price_el.select_one(".a-price-whole").get_text() if price_el.select_one(".a-price-whole") else "")
            fraction = _clean_text(price_el.select_one(".a-price-fraction").get_text() if price_el.select_one(".a-price-fraction") else "")
            symbol = _clean_text(price_el.select_one(".a-price-symbol").get_text() if price_el.select_one(".a-price-symbol") else "")
            if whole:
                price = _parse_price_text(f"{symbol}{whole}.{fraction or '00'}", marketplace)
                if price:
                    return price
    return ""


def _extract_rating(soup: BeautifulSoup) -> str:
    selectors = [
        "#acrPopover span.a-icon-alt",
        "span[data-hook='rating-out-of-text']",
        "i.a-icon-star span.a-icon-alt",
        "#averageCustomerReviews span.a-icon-alt",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            text = _clean_text(el.get_text())
            match = re.search(r"([\d.]+)", text)
            if match:
                return match.group(1)
    return ""


def _extract_review_count(soup: BeautifulSoup) -> str:
    selectors = [
        "#acrCustomerReviewText",
        "span[data-hook='total-review-count']",
        "#averageCustomerReviews #acrCustomerReviewLink",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            text = _clean_text(el.get_text())
            match = re.search(r"([\d,]+)", text)
            if match:
                return match.group(1).replace(",", "")
    return ""


def _extract_coupon(soup: BeautifulSoup) -> str:
    selectors = [
        "#couponText",
        "#couponBadgeRegularVpc_feature_div",
        "#promoPriceBlockMessage_feature_div",
        ".couponBadge",
        ".couponLabel",
        "label[id*='coupon']",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if not el:
            continue
        text = _clean_text(el.get_text(" ", strip=True))
        if text and re.search(r"coupon|save|savings|apply|clip|off|优惠|折扣", text, flags=re.I):
            return text[:180]
    page_text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"((?:save|savings|coupon|clip coupon|apply coupon)[^.。]{0,80})", page_text, flags=re.I)
    return _clean_text(match.group(1))[:180] if match else ""


def _extract_deal_status(soup: BeautifulSoup) -> str:
    selectors = [
        "#dealBadge_feature_div",
        "#dealBadgeSupportingText",
        "#gb_deals_feature_div",
        ".dealBadge",
        ".badge-link",
        "span[id*='deal']",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if not el:
            continue
        text = _clean_text(el.get_text(" ", strip=True))
        if text and re.search(r"deal|limited time|prime|lightning|today|限时|促销", text, flags=re.I):
            return text[:180]
    page_text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"((?:limited time deal|lightning deal|prime exclusive deal|deal)[^.。]{0,80})", page_text, flags=re.I)
    return _clean_text(match.group(1))[:180] if match else ""


def _extract_product_details(soup: BeautifulSoup) -> dict:
    details: dict[str, str] = {}

    def add_detail(label: str, value: str) -> None:
        label = _clean_text(label).strip(" :：")
        value = _clean_text(value)
        if label and value and len(value) < 300:
            details[label] = value

    for table_sel in ["#productDetails_detailBullets_sections1", "#productDetails_techSpec_section_1", "#prodDetails"]:
        table = soup.select_one(table_sel)
        if not table:
            continue
        for row in table.select("tr"):
            header = row.select_one("th")
            value = row.select_one("td")
            if header and value:
                add_detail(header.get_text(), value.get_text(" ", strip=True))

    for li in soup.select("#detailBulletsWrapper_feature_div li, #detailBullets_feature_div li"):
        text = _clean_text(li.get_text(" ", strip=True))
        if ":" in text:
            label, value = text.split(":", 1)
            add_detail(label, value)
        elif "：" in text:
            label, value = text.split("：", 1)
            add_detail(label, value)

    return details


def _extract_date_first_available(details: dict) -> str:
    for key, value in details.items():
        norm = key.lower()
        if "date first available" in norm or "first available" in norm or "首次" in key or "发布日期" in key:
            return value
    return ""


def _extract_rating_histogram(soup: BeautifulSoup) -> dict:
    histogram: dict[str, str] = {}
    for star in range(5, 0, -1):
        selectors = [
            f'tr[aria-label*="{star} star"]',
            f'a[aria-label*="{star} star"]',
            f'a[title*="{star} star"]',
        ]
        found = ""
        for sel in selectors:
            el = soup.select_one(sel)
            if not el:
                continue
            text = _clean_text(" ".join([el.get("aria-label", ""), el.get("title", ""), el.get_text(" ", strip=True)]))
            match = re.search(r"(\d{1,3})\s*%", text)
            if match:
                found = f"{match.group(1)}%"
                break
        if not found:
            row = soup.select_one(f"#histogramTable tr:nth-child({6-star})")
            if row:
                match = re.search(r"(\d{1,3})\s*%", _clean_text(row.get_text(" ", strip=True)))
                if match:
                    found = f"{match.group(1)}%"
        if found:
            histogram[f"{star}_star"] = found
    return histogram


def _extract_low_star_reviews_from_soup(soup: BeautifulSoup, limit: int = 20) -> list[dict]:
    reviews: list[dict] = []
    for item in soup.select('[data-hook="review"]')[:limit * 2]:
        rating_text = _clean_text(
            (item.select_one('[data-hook="review-star-rating"] span') or item.select_one('[data-hook="cmps-review-star-rating"] span') or item.select_one(".a-icon-alt") or item).get_text(" ", strip=True)
        )
        rating_match = re.search(r"([1-5](?:\.\d)?)", rating_text)
        rating = float(rating_match.group(1)) if rating_match else 0
        if rating > 3 or rating <= 0:
            continue
        title = _clean_text((item.select_one('[data-hook="review-title"]') or item.select_one(".review-title") or item).get_text(" ", strip=True))
        body = _clean_text((item.select_one('[data-hook="review-body"] span') or item.select_one('[data-hook="review-body"]') or item).get_text(" ", strip=True))
        date = _clean_text((item.select_one('[data-hook="review-date"]') or item.select_one(".review-date") or item).get_text(" ", strip=True))
        verified = bool(item.select_one('[data-hook="avp-badge"]'))
        if body:
            reviews.append({
                "rating": rating,
                "title": title[:200],
                "body": body[:2000],
                "date": date[:120],
                "verified": verified,
            })
        if len(reviews) >= limit:
            break
    return reviews


def _extract_image_urls(soup: BeautifulSoup, limit: int = 12) -> list[str]:
    urls: list[str] = []
    landing = soup.select_one("#landingImage")
    if landing:
        dynamic = landing.get("data-a-dynamic-image")
        if dynamic:
            try:
                urls.extend(list(json.loads(dynamic).keys()))
            except Exception:
                pass
        for attr in ["data-old-hires", "src"]:
            value = landing.get(attr)
            if value:
                urls.append(value)
    for img in soup.select("#altImages img"):
        src = img.get("src") or ""
        if src:
            urls.append(re.sub(r"\._[A-Z0-9_,]+_\.", ".", src))
    seen: set[str] = set()
    clean = []
    for url in urls:
        if "media-amazon" in url and url not in seen:
            seen.add(url)
            clean.append(url)
        if len(clean) >= limit:
            break
    return clean


def _extract_bullet_points(soup: BeautifulSoup) -> list:
    bullets = []
    feature_div = soup.select_one("#feature-bullets")
    if feature_div:
        items = feature_div.select("li span.a-list-item")
        for item in items:
            text = _clean_text(item.get_text())
            if text and len(text) > 5 and "see more" not in text.lower():
                bullets.append(text)
    return bullets[:5]


def _extract_brand(soup: BeautifulSoup) -> str:
    for sel in ["#bylineInfo", "a#bylineInfo", "span.author a"]:
        el = soup.select_one(sel)
        if el:
            text = _clean_text(el.get_text())
            if re.search(r"amazon|亚马逊", text, flags=re.I):
                return "Amazon"
            text = re.sub(r"^(Visit the |Brand:\s*)", "", text, flags=re.IGNORECASE)
            text = re.sub(r"^(访问|Visit)\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*Store$", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*商店$", "", text)
            if text:
                return text
    return ""


def _detect_seller_type(title: str, brand: str, soup: BeautifulSoup) -> str:
    blob = " ".join([
        title or "",
        brand or "",
        _clean_text((soup.select_one("#bylineInfo") or soup).get_text(" ", strip=True)[:500]),
        _clean_text((soup.select_one("#merchant-info") or soup).get_text(" ", strip=True)[:500]),
    ]).lower()
    amazon_device_terms = [
        "echo show", "echo dot", "echo spot", "echo studio", "fire tv", "kindle",
        "alexa", "ring video", "blink outdoor", "amazon basics", "amazonbasics",
    ]
    if "amazon" in blob or "亚马逊" in blob:
        if any(term in blob for term in amazon_device_terms):
            return "Amazon自营/平台生态强绑定"
        if "ships from amazon" in blob or "sold by amazon" in blob or "sold by amazon.com" in blob:
            return "Amazon自营"
    return "第三方/待确认"


def _detect_platform_ecosystem(title: str, brand: str) -> bool:
    blob = f"{title} {brand}".lower()
    return any(term in blob for term in [
        "echo show", "echo dot", "echo spot", "echo studio", "alexa", "fire tv", "kindle", "ring video", "blink outdoor"
    ])


def _extract_category(soup: BeautifulSoup) -> str:
    breadcrumb = soup.select_one("#wayfinding-breadcrumbs_container")
    if breadcrumb:
        items = breadcrumb.select("a")
        if items:
            cats = [_clean_text(a.get_text()) for a in items]
            return " > ".join(cats) if cats else ""
    return ""


def _extract_bsr(soup: BeautifulSoup) -> dict:
    result = {"rank": "", "category": ""}
    details = soup.select_one("#productDetails_detailBullets_sections1")
    if details:
        for row in details.select("tr"):
            header = row.select_one("th")
            value = row.select_one("td")
            if header and value:
                h_text = _clean_text(header.get_text()).lower()
                if "best seller" in h_text or "ranking" in h_text:
                    v_text = _clean_text(value.get_text())
                    match = re.search(r"#?([\d,]+)", v_text)
                    if match:
                        result["rank"] = match.group(1).replace(",", "")
                    cat_match = re.search(r"in\s+(.+?)(?:\s*\(|$)", v_text)
                    if cat_match:
                        result["category"] = cat_match.group(1).strip()
                    break
    if not result["rank"]:
        for li in soup.select("#detailBulletsWrapper_feature_div li"):
            text = _clean_text(li.get_text())
            if "best seller" in text.lower() or "ranking" in text.lower():
                match = re.search(r"#?([\d,]+)", text)
                if match:
                    result["rank"] = match.group(1).replace(",", "")
                cat_match = re.search(r"in\s+(.+?)(?:\s*\(|$)", text)
                if cat_match:
                    result["category"] = cat_match.group(1).strip()
                break
    return result


def _extract_image_count(soup: BeautifulSoup) -> str:
    thumbnails = soup.select("#altImages li.a-spacing-small.item")
    if thumbnails:
        return str(len(thumbnails))
    thumbnails = soup.select("#altImages img")
    if thumbnails:
        return str(len(thumbnails))
    return ""


def _check_video(soup: BeautifulSoup) -> bool:
    if soup.select_one("#video-block") or soup.select_one(".videoBlock"):
        return True
    for thumb in soup.select("#altImages li"):
        if "videoThumbnail" in str(thumb.get("class", [])):
            return True
    return False


APLUS_SELECTORS = [
    "#aplus",
    "#aplusProductDescription",
    "#aplus_feature_div",
    "#aplusBrandStory_feature_div",
    "#aplus-3p-fixed-recipe-expander-inner",
    "#aplus3p_feature_div",
    "#aplus-3p_feature_div",
    "#m-aplus",
    ".aplus-v2",
    ".aplus-module",
    ".aplus-brand-story",
    ".aplus-comparison-table",
    ".premium-aplus",
    "[data-feature-name='aplus']",
    "[data-cel-widget*='aplus']",
    "[id*='aplus']",
    "[class*='aplus']",
]


def _get_aplus_sections(soup: BeautifulSoup) -> list:
    sections = []
    seen: set[int] = set()
    for sel in APLUS_SELECTORS:
        for section in soup.select(sel):
            sid = id(section)
            if sid not in seen:
                seen.add(sid)
                sections.append(section)
    return sections


def _extract_aplus_image_urls(soup: BeautifulSoup, limit: int = 20) -> list[str]:
    urls: list[str] = []
    for section in _get_aplus_sections(soup):
        for img in section.select("img"):
            for attr in ["data-src", "data-a-hires", "data-old-hires", "src"]:
                value = img.get(attr)
                if value and "media-amazon" in value:
                    urls.append(re.sub(r"\._[A-Z0-9_,]+_\.", ".", value))
    seen: set[str] = set()
    clean: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            clean.append(url)
        if len(clean) >= limit:
            break
    return clean


def _check_aplus(soup: BeautifulSoup) -> bool:
    sections = _get_aplus_sections(soup)
    if not sections:
        return False
    for section in sections:
        text = _clean_text(section.get_text(" ", strip=True))
        image_count = len(section.select("img"))
        if image_count >= 1 or len(text) >= 80:
            return True
    return bool(_extract_aplus_image_urls(soup, limit=1))


def _extract_aplus_content(soup: BeautifulSoup) -> str:
    """Extract actual text content from A+ / Enhanced Brand Content sections."""
    aplus_texts = []
    image_count = 0

    for section in _get_aplus_sections(soup):
        # 1. 提取标题（H1-H5 + 模块标题）
        for heading in section.select("h1, h2, h3, h4, h5, .aplus-module-title, .a-size-large, .a-text-bold"):
            text = _clean_text(heading.get_text())
            if text and len(text) > 2:
                aplus_texts.append(f"📌 {text}")

        # 2. 提取段落文本（更全面的选择器）
        para_selectors = [
            "p", 
            ".aplus-module-text", 
            ".aplus-module-text-block", 
            "span.a-text-bold", 
            ".a-size-base",
            ".a-size-medium",
            ".a-row",
            "li",
        ]
        for para in section.select(", ".join(para_selectors)):
            text = _clean_text(para.get_text())
            if text and len(text) > 10:
                if text not in aplus_texts:
                    aplus_texts.append(text)

        # 3. 提取列表项（要点/特性）
        for li in section.select("ul li, ol li, .a-list-item"):
            text = _clean_text(li.get_text())
            if text and len(text) > 5:
                if f"• {text}" not in aplus_texts and text not in aplus_texts:
                    aplus_texts.append(f"• {text}")

        # 4. 提取图片alt文本（重要！A+大量使用图片）
        for img in section.select("img[alt]"):
            alt = _clean_text(img.get("alt", ""))
            src = img.get("src", "")
            if alt and len(alt) > 5:
                alt_lower = alt.lower()
                # 过滤无用的alt
                if not any(kw in alt_lower for kw in ["image", "photo", "picture", "click to", "default"]):
                    aplus_texts.append(f"[🖼️ 图片: {alt}]")
                    image_count += 1
            elif src and "media-amazon" in src:
                image_count += 1

        # 5. 提取表格内容（对比表）
        for table in section.select("table"):
            rows = table.select("tr")
            for row in rows[:8]:  # 只取前8行避免过大
                cells = row.select("th, td")
                row_text = " | ".join([_clean_text(c.get_text()) for c in cells if _clean_text(c.get_text())])
                if row_text and len(row_text) > 5:
                    aplus_texts.append(f"📊 {row_text}")

    # 去重和清理
    seen = set()
    unique_texts = []
    for t in aplus_texts:
        t_lower = t.lower().strip()
        if t_lower not in seen and len(t) > 3:
            seen.add(t_lower)
            unique_texts.append(t)

    content = " ".join(unique_texts[:50])  # 增加到50项
    
    # 添加图片计数信息
    url_count = len(_extract_aplus_image_urls(soup))
    if url_count > image_count:
        image_count = url_count
    if image_count > 0:
        content = f"[A+图片数: {image_count}] " + content

    if len(content) > 3000:  # 增加到3000字符
        content = content[:3000] + "..."

    return content


def _extract_bought_count(soup: BeautifulSoup) -> str:
    """Extract 'X bought in past month' social proof from Amazon product page.

    Amazon displays this as e.g. '1K+ bought in past month', '10K+ bought in past month',
    '50+ bought in past month', etc. in various locations on the page.
    """
    # Common selectors where Amazon shows purchase count
    selectors = [
        "#social-proofing-faceout-title-tk_bought span",
        "#socialProofingAsinFaceout_feature_div span",
        "#social-proofing-faceout-title-tk_bought",
        "#socialProofingAsinFaceout_feature_div",
        "span[data-social-proof]",
    ]

    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            text = _clean_text(el.get_text())
            if "bought" in text.lower():
                return text

    # Fallback: search entire page text for the pattern
    # Look for patterns like "1K+ bought in past month", "50+ bought in past month"
    page_text = soup.get_text()
    patterns = [
        re.compile(r'(\d+[KkMm]?\+?\s*bought\s+in\s+past\s+month)', re.IGNORECASE),
        re.compile(r'(\d[\d,.]*[KkMm]?\+?\s*bought\s+in\s+past\s+month)', re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.search(page_text)
        if match:
            return _clean_text(match.group(1))

    return ""


def _is_captcha_page(html: str) -> bool:
    lower = html.lower()
    signals = [
        "captcha", "robot check", "type the characters you see",
        "sorry, we just need to make sure",
        "enter the characters you see below",
        "to discuss automated access",
    ]
    return any(s in lower for s in signals)


def _parse_product_page(html: str, marketplace: str = "US") -> Optional[dict]:
    """Parse product data from HTML. Returns None if not a valid product page."""
    if _is_captcha_page(html):
        return None
    if len(html) < 10000:
        return None

    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup)
    if not title:
        return None

    brand = _extract_brand(soup)
    bsr = _extract_bsr(soup)
    details = _extract_product_details(soup)
    has_aplus = _check_aplus(soup)
    aplus_content = _extract_aplus_content(soup) if has_aplus else ""
    aplus_image_urls = _extract_aplus_image_urls(soup) if has_aplus else []
    bought_count = _extract_bought_count(soup)
    symbol, code = MARKETPLACE_CURRENCIES.get(marketplace, ("$", "USD"))
    return {
        "title": title,
        "brand": brand,
        "category": _extract_category(soup),
        "price": _extract_price(soup, marketplace),
        "price_currency": code,
        "rating": _extract_rating(soup),
        "review_count": _extract_review_count(soup),
        "coupon": _extract_coupon(soup),
        "deal_status": _extract_deal_status(soup),
        "rating_histogram": _extract_rating_histogram(soup),
        "product_details": details,
        "date_first_available": _extract_date_first_available(details),
        "bullet_points": _extract_bullet_points(soup),
        "image_count": _extract_image_count(soup),
        "image_urls": _extract_image_urls(soup),
        "has_video": _check_video(soup),
        "has_a_plus": has_aplus,
        "aplus_content": aplus_content,
        "aplus_image_count": str(len(aplus_image_urls)) if aplus_image_urls else "",
        "aplus_image_urls": aplus_image_urls,
        "bsr_rank": bsr["rank"],
        "bsr_category": bsr["category"],
        "bought_count": bought_count,
        "low_star_reviews": _extract_low_star_reviews_from_soup(soup),
        "seller_type": _detect_seller_type(title, brand, soup),
        "platform_ecosystem": _detect_platform_ecosystem(title, brand),
        "brand_monopoly_risk": bool(_detect_platform_ecosystem(title, brand) and _num_from_text(_extract_review_count(soup)) >= 10000),
    }


def _num_from_text(value: str) -> float:
    try:
        return float(re.sub(r"[^0-9.]", "", str(value)) or 0)
    except Exception:
        return 0


async def fetch_low_star_reviews(asin: str, marketplace: str = "US", max_pages_per_star: int = 2) -> list[dict]:
    """Fetch 1-3 star review pages as evidence; best-effort and non-fatal."""
    domain = MARKETPLACE_DOMAINS.get(marketplace, "www.amazon.com")
    lang = ACCEPT_LANG.get(marketplace, "en-US,en;q=0.9")
    filters = [("three_star", 3), ("two_star", 2), ("one_star", 1)]
    reviews: list[dict] = []
    seen: set[str] = set()

    async def parse_html(html: str) -> None:
        soup = BeautifulSoup(html, "html.parser")
        for review in _extract_low_star_reviews_from_soup(soup, limit=20):
            key = f"{review.get('rating')}|{review.get('title')}|{review.get('body')[:80]}"
            if key not in seen:
                seen.add(key)
                reviews.append(review)

    try:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate=random.choice(["chrome131", "chrome124", "chrome120", "chrome"])) as session:
            headers = _build_desktop_headers(lang)
            headers["Cookie"] = "lc-main=en_US; i18n-prefs=USD"
            for filter_name, _star in filters:
                for page in range(1, max_pages_per_star + 1):
                    url = f"https://{domain}/product-reviews/{asin}?filterByStar={filter_name}&reviewerType=all_reviews&sortBy=recent&pageNumber={page}&language=en_US"
                    resp = await session.get(url, headers=headers, timeout=10)
                    if resp.status_code == 200 and resp.text:
                        await parse_html(resp.text)
                    if len(reviews) >= 60:
                        return reviews[:60]
                    await asyncio.sleep(random.uniform(0.2, 0.5))
    except Exception as exc:
        logger.info("low-star review fetch skipped for %s: %s", asin, exc)

    return reviews[:60]


# ------------------------------------------------------------------ #
#  Strategy 1: curl-cffi with Chrome TLS impersonation                 #
# ------------------------------------------------------------------ #

def _build_desktop_headers(lang: str) -> dict:
    """Build realistic desktop Chrome headers."""
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": lang,
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
    }


def _build_mobile_headers(lang: str) -> dict:
    """Build realistic mobile Chrome headers."""
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": lang,
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": '"Android"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }


async def _strategy_curl_cffi(asin: str, domain: str, marketplace: str) -> Optional[dict]:
    """Use curl-cffi to impersonate Chrome's TLS fingerprint.

    Tries desktop UA first, then mobile UA as fallback.
    Each attempt uses a different impersonation version.
    """
    try:
        from curl_cffi.requests import AsyncSession
    except ImportError:
        logger.info("curl-cffi not available, skipping strategy")
        return None

    url = f"https://{domain}/dp/{asin}"
    lang = ACCEPT_LANG.get(marketplace, "en-US,en;q=0.9")

    # Attempt A: Desktop Chrome
    impersonate_choices = ["chrome131", "chrome124", "chrome120", "chrome116", "chrome"]
    impersonate = random.choice(impersonate_choices)

    try:
        async with AsyncSession(impersonate=impersonate) as session:
            headers = _build_desktop_headers(lang)

            # Visit homepage first to get cookies
            try:
                await session.get(
                    f"https://{domain}/",
                    headers=headers,
                    timeout=5,
                )
                logger.info(f"curl-cffi desktop: Got session cookies from {domain}")
                await asyncio.sleep(random.uniform(0.5, 1.5))
            except Exception:
                pass

            resp = await session.get(url, headers=headers, timeout=8)

            if resp.status_code == 200:
                html = resp.text
                parsed = _parse_product_page(html, marketplace)
                if parsed:
                    logger.info(f"curl-cffi desktop ({impersonate}) succeeded for {asin}: {parsed['title'][:60]}")
                    return parsed
                else:
                    logger.info(f"curl-cffi desktop: Page blocked/invalid for {asin} (size={len(html)}, captcha={_is_captcha_page(html)})")
            else:
                logger.info(f"curl-cffi desktop: HTTP {resp.status_code} for {asin}")
    except Exception as e:
        logger.info(f"curl-cffi desktop strategy failed for {asin}: {e}")

    # Small delay between attempts
    await asyncio.sleep(random.uniform(0.5, 1.0))

    # Attempt B: Mobile Chrome (Amazon mobile pages are simpler, less blocking)
    mobile_impersonate = random.choice(["chrome131", "chrome120", "chrome"])
    mobile_ua = random.choice(_MOBILE_UAS)

    try:
        async with AsyncSession(impersonate=mobile_impersonate) as session:
            headers = _build_mobile_headers(lang)
            headers["User-Agent"] = mobile_ua

            # Use mobile domain for better results
            mobile_domain = domain.replace("www.", "m.")
            mobile_url = f"https://{mobile_domain}/dp/{asin}"

            try:
                await session.get(
                    f"https://{mobile_domain}/",
                    headers=headers,
                    timeout=12,
                )
                await asyncio.sleep(random.uniform(0.3, 0.8))
            except Exception:
                pass

            resp = await session.get(mobile_url, headers=headers, timeout=8)

            if resp.status_code == 200:
                html = resp.text
                parsed = _parse_product_page(html, marketplace)
                if parsed:
                    logger.info(f"curl-cffi mobile ({mobile_impersonate}) succeeded for {asin}: {parsed['title'][:60]}")
                    return parsed
                else:
                    logger.info(f"curl-cffi mobile: Page blocked/invalid for {asin} (size={len(html)})")
            else:
                logger.info(f"curl-cffi mobile: HTTP {resp.status_code} for {asin}")
    except Exception as e:
        logger.info(f"curl-cffi mobile strategy failed for {asin}: {e}")

    return None


# ------------------------------------------------------------------ #
#  Strategy 2: httpx with realistic headers (lightweight fallback)     #
# ------------------------------------------------------------------ #

async def _strategy_httpx(asin: str, domain: str, marketplace: str) -> Optional[dict]:
    """Use httpx as a lightweight fallback. No TLS impersonation but works everywhere."""
    try:
        import httpx
    except ImportError:
        logger.info("httpx not available, skipping strategy")
        return None

    url = f"https://{domain}/dp/{asin}"
    lang = ACCEPT_LANG.get(marketplace, "en-US,en;q=0.9")
    ua = random.choice(_DESKTOP_UAS)

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": lang,
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "DNT": "1",
    }

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(15.0, connect=5.0),  # ⚡ 加快超时
            http2=False,
        ) as client:
            # Visit homepage first for cookies
            try:
                await client.get(f"https://{domain}/", headers=headers)
                await asyncio.sleep(random.uniform(0.5, 1.5))
            except Exception:
                pass

            resp = await client.get(url, headers=headers)

            if resp.status_code == 200:
                html = resp.text
                parsed = _parse_product_page(html, marketplace)
                if parsed:
                    logger.info(f"httpx succeeded for {asin}: {parsed['title'][:60]}")
                    return parsed
                else:
                    logger.info(f"httpx: Page blocked/invalid for {asin} (size={len(html)})")
            else:
                logger.info(f"httpx: HTTP {resp.status_code} for {asin}")
    except Exception as e:
        logger.info(f"httpx strategy failed for {asin}: {e}")

    return None


# ------------------------------------------------------------------ #
#  Strategy 3: Playwright headless browser (optional)                  #
# ------------------------------------------------------------------ #

async def _strategy_playwright(asin: str, domain: str, marketplace: str) -> Optional[dict]:
    """Use Playwright to render the page in a real headless browser.
    Gracefully skips if playwright is not installed or browsers not available.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.info("Playwright not available, skipping strategy")
        return None

    url = f"https://{domain}/dp/{asin}"
    lang = ACCEPT_LANG.get(marketplace, "en-US,en;q=0.9")
    ua = random.choice(_DESKTOP_UAS)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )

            context = await browser.new_context(
                user_agent=ua,
                locale=lang.split(",")[0].split(";")[0],
                viewport={"width": 1920, "height": 1080},
                java_script_enabled=True,
            )

            # Remove webdriver detection
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """)

            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)  # ⚡ 减半

                try:
                    await page.wait_for_selector("#productTitle", timeout=5000)  # ⚡ 减半
                except Exception:
                    await asyncio.sleep(2)

                html = await page.content()

            finally:
                await browser.close()

            parsed = _parse_product_page(html, marketplace)
            if parsed:
                logger.info(f"Playwright succeeded for {asin}: {parsed['title'][:60]}")
                return parsed
            else:
                logger.info(f"Playwright: Page blocked or invalid for {asin} (size={len(html)})")

    except Exception as e:
        logger.info(f"Playwright strategy failed for {asin}: {e}")

    return None


# ------------------------------------------------------------------ #
#  Main entry point                                                    #
# ------------------------------------------------------------------ #

async def _scrape_with_timeout(asin: str, marketplace: str, domain: str) -> Optional[dict]:
    """Inner scrape function with strategy order."""
    # --- Strategy 1: curl-cffi (desktop + mobile) FASTEST ---
    parsed = await _strategy_curl_cffi(asin, domain, marketplace)
    if parsed:
        return parsed

    # --- Strategy 2: httpx lightweight ---
    parsed = await _strategy_httpx(asin, domain, marketplace)
    if parsed:
        return parsed

    # --- Strategy 3: SKIPPED Playwright (too slow! ⚡) ---
    # 跳过Playwright，抓取速度优先！

    return None

async def scrape_amazon_product(asin: str, marketplace: str = "US") -> dict:
    """
    Scrape product data from Amazon with multiple strategies and GLOBAL TIMEOUT.

    ⚡ PERFORMANCE OPTIMIZED: 45秒总超时，跳过最慢的Playwright策略
    1. curl-cffi (Chrome TLS impersonation) - FASTEST
    2. httpx with realistic headers - lightweight fallback
    3. Returns failure → caller falls back to AI

    Returns a dict with scraped data or failure indicators.
    """
    domain = MARKETPLACE_DOMAINS.get(marketplace, "www.amazon.com")

    result = {
        "asin": asin,
        "url": f"https://{domain}/dp/{asin}",
        "title": "",
        "brand": "",
        "category": "",
        "price": "",
        "rating": "",
        "review_count": "",
        "bsr_rank": "",
        "bsr_category": "",
        "bullet_points": [],
        "image_count": "",
        "has_video": False,
        "has_a_plus": False,
        "data_source": "scrape_failed",
        "scrape_success": False,
    }

    try:
        # ⚡ 全局超时：45秒必须完成
        parsed = await asyncio.wait_for(
            _scrape_with_timeout(asin, marketplace, domain),
            timeout=45
        )
        if parsed:
            if not parsed.get("low_star_reviews"):
                parsed["low_star_reviews"] = await fetch_low_star_reviews(asin, marketplace)
            result.update(parsed)
            result["data_source"] = "amazon_scrape"
            result["scrape_success"] = True
            return result
    except asyncio.TimeoutError:
        logger.warning(f"⏰ Scrape GLOBAL TIMEOUT for {asin} after 45s")
        result["data_source"] = "scrape_timeout"
    except Exception as e:
        logger.warning(f"Scrape error for {asin}: {e}")

    # All strategies failed
    logger.warning(f"All scraping strategies failed for {asin} on {marketplace}")
    return result
