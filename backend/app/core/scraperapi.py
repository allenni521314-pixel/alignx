from __future__ import annotations
"""ScraperAPI provider — Amazon product and search capture."""

import json
import re
import httpx
from app.config import get_settings
from app.core.capture import CaptureResult
from app.core.listing_images import extract_slot_image_texts

settings = get_settings()


class ScraperAPIProvider:
    """Captures Amazon data via ScraperAPI proxy endpoint."""

    def __init__(self) -> None:
        self.key = settings.scraperapi_key
        self.client = httpx.AsyncClient(timeout=60.0)

    # ── Product page by ASIN ──────────────────────────

    async def capture_product_by_asin(self, asin: str, marketplace: str = "amazon.com") -> CaptureResult:
        url = f"https://www.{marketplace}/dp/{asin}"
        return await self._fetch(url, asin)

    async def capture_product_by_url(self, url: str, marketplace: str = "amazon.com") -> CaptureResult:
        asin = self._extract_asin(url)
        if not asin:
            return CaptureResult(capture_status="failed", capture_provider="scraperapi", error_message=f"Could not extract ASIN from URL: {url}")
        return await self.capture_product_by_asin(asin, marketplace)

    # ── Top 20 by keyword ─────────────────────────────

    async def capture_top20_by_keyword(self, keyword: str, marketplace: str = "amazon.com") -> CaptureResult:
        url = f"https://www.{marketplace}/s?k={keyword.replace(' ', '+')}"
        return await self._fetch(url, keyword, is_search=True)

    # ── Core fetch ────────────────────────────────────

    async def _fetch(self, amazon_url: str, identifier: str, is_search: bool = False) -> CaptureResult:
        try:
            proxy_url = f"https://api.scraperapi.com/?api_key={self.key}&url={amazon_url}&country_code=us"
            resp = await self.client.get(proxy_url)
            resp.raise_for_status()
            html = resp.text

            if is_search:
                return self._parse_search_html(html, identifier)
            else:
                result = self._parse_product_html(html, identifier)
                # OCR: extract text from product images
                if result.capture_status != "failed":
                    await self._ocr_images(result)
                return result
        except Exception as e:
            return CaptureResult(capture_status="failed", capture_provider="scraperapi", error_message=str(e))

    # ── HTML parsers ──────────────────────────────────

    def _parse_product_html(self, html: str, asin: str) -> CaptureResult:
        """Extract listing fields from Amazon product page HTML."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        fields = {}
        missing = []

        # Title
        title_el = soup.select_one("#productTitle")
        title = title_el.text.strip() if title_el else None
        if title:
            fields["title"] = title
        else:
            missing.append("title")

        # Price
        price_whole = soup.select_one(".a-price-whole")
        price_fraction = soup.select_one(".a-price-fraction")
        if price_whole:
            price_str = price_whole.text.strip().replace(",", "").rstrip(".")
            if price_fraction:
                price_str += "." + price_fraction.text.strip()
            fields["price"] = f"${price_str}" if not price_str.startswith("$") else price_str
            try:
                fields["price_value"] = float(price_str)
            except ValueError:
                fields["price_value"] = None
            fields["currency"] = "USD"
        else:
            missing.append("price")

        # Rating
        rating_el = soup.select_one('[data-hook="rating-out-of-text"]') or soup.select_one(".a-icon-star .a-icon-alt")
        if rating_el:
            import re
            match = re.search(r"(\d+\.?\d*)", rating_el.text)
            if match:
                fields["rating"] = float(match.group(1))
        else:
            missing.append("rating")

        # Review count
        review_el = soup.select_one("#acrCustomerReviewText")
        if review_el:
            import re
            match = re.search(r"(\d[\d,]*)", review_el.text)
            if match:
                fields["review_count"] = int(match.group(1).replace(",", ""))
        else:
            missing.append("review_count")

        # Main image
        img_el = soup.select_one("#landingImage") or soup.select_one(".a-dynamic-image")
        if img_el:
            main_candidates = self._image_candidates_from_tag(img_el)
            if main_candidates:
                fields["main_image"] = main_candidates[0]

        # Image URLs
        alt_images = soup.select("#altImages .item img, #imageBlockThumbs img")
        if alt_images:
            image_urls = []
            for img in alt_images:
                image_urls.extend(self._image_candidates_from_tag(img))
            main_image = fields.get("main_image")
            fields["image_urls"] = [
                url for url in dict.fromkeys(image_urls)
                if url and url != main_image
            ]

        # Bullet points
        bullets = soup.select("#feature-bullets li span.a-list-item")
        if bullets:
            fields["bullet_points"] = [b.text.strip() for b in bullets if b.text.strip()]
        else:
            missing.append("bullet_points")

        # A+ content
        aplus = soup.select("#aplus .aplus-v2")
        if aplus:
            fields["aplus_content"] = [a.text.strip()[:500] for a in aplus]

        # Bought in past month
        bipm = soup.select_one("#social-proofing-faceout-title-tk_bought span")
        if bipm:
            fields["bought_in_past_month_raw"] = bipm.text.strip()

        completeness = 1.0 - (len(missing) / max(len(fields) + len(missing), 1))
        return CaptureResult(
            raw_html=html,
            extracted_fields=fields,
            missing_fields=missing,
            capture_status="partial" if missing else "success",
            capture_provider="scraperapi",
            data_completeness_score=round(completeness, 2),
        )

    def _parse_search_html(self, html: str, keyword: str) -> CaptureResult:
        """Extract top results from Amazon search page HTML."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        items = []

        results = soup.select('[data-component-type="s-search-result"]')
        for item in results[:20]:
            asin = item.get("data-asin")
            if not asin:
                continue

            title_el = item.select_one("h2 a span")
            # Improved price extraction - handle multiple formats
            price_text = ""
            price_whole = item.select_one(".a-price-whole")
            price_fraction = item.select_one(".a-price-fraction")
            if price_whole:
                price_text = price_whole.text.strip()
                if price_fraction:
                    price_text += "." + price_fraction.text.strip()
            if not price_text:
                price_offscreen = item.select_one(".a-price .a-offscreen")
                if price_offscreen:
                    price_text = price_offscreen.text.strip()
            if not price_text:
                price_range = item.select_one(".a-price-range")
                if price_range:
                    price_text = price_range.text.strip()

            rating_el = item.select_one(".a-icon-alt")
            # Review count - multiple selectors
            review_el = (
                item.select_one(".a-size-base.s-underline-text") or
                item.select_one(".a-size-small .a-link-normal") or
                item.select_one("[data-cy='reviews-block'] .a-size-base") or
                item.select_one(".a-row.a-size-small span[aria-label]")
            )
            review_text = review_el.get("aria-label") or review_el.text if review_el else ""
            review_count = None
            if review_text:
                import re
                match = re.search(r"([\d,]+)", review_text.replace(",", ""))
                if match:
                    try:
                        review_count = int(match.group(1))
                    except:
                        pass

            img_el = item.select_one("img.s-image")

            items.append({
                "asin": asin,
                "title": title_el.text.strip() if title_el else "",
                "price": price_text,
                "rating": float(rating_el.text.split()[0]) if rating_el else None,
                "review_count": review_count,
                "image": img_el.get("src", "") if img_el else "",
            })

        return CaptureResult(
            raw_html=html,
            extracted_fields={"keyword": keyword, "results": items, "total": len(items)},
            capture_status="success" if items else "partial",
            capture_provider="scraperapi",
            data_completeness_score=1.0 if items else 0.0,
        )

    # ── Helpers ───────────────────────────────────────

    async def _ocr_images(self, result: CaptureResult) -> None:
        """Extract text from product images using vision AI."""
        try:
            image_texts = await extract_slot_image_texts(result.extracted_fields)
            if image_texts:
                result.extracted_fields["ocr_image_texts"] = image_texts
        except Exception:
            pass

    def _image_candidates_from_tag(self, tag) -> list[str]:
        urls: list[str] = []
        dynamic = tag.get("data-a-dynamic-image")
        if dynamic:
            try:
                parsed = json.loads(dynamic)
                if isinstance(parsed, dict):
                    items = sorted(
                        parsed.items(),
                        key=lambda item: item[1][0] * item[1][1] if isinstance(item[1], list) and len(item[1]) >= 2 else 0,
                        reverse=True,
                    )
                    urls.extend([url for url, _ in items])
            except Exception:
                pass

        for attr in ("data-old-hires", "data-a-src", "src"):
            url = tag.get(attr)
            if url:
                urls.append(url)

        cleaned = []
        for url in urls:
            normalized = self._normalize_image_url(url)
            if self._is_product_image_url(normalized):
                cleaned.append(normalized)
        return list(dict.fromkeys(cleaned))

    def _normalize_image_url(self, url: str) -> str:
        return re.sub(r"\._[^.]+_\.", ".", url)

    def _is_product_image_url(self, url: str) -> bool:
        return url.startswith("http") and "media-amazon.com/images/I/" in url

    def _extract_asin(self, url: str) -> str | None:
        match = re.search(r"/dp/([A-Z0-9]{10})", url)
        return match.group(1) if match else None
