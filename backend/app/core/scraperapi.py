from __future__ import annotations
"""ScraperAPI provider — Amazon product and search capture."""

import json
import httpx
from app.config import get_settings
from app.core.capture import CaptureResult

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
            fields["main_image"] = img_el.get("src") or img_el.get("data-old-hires")

        # Image URLs
        alt_images = soup.select("#altImages .item img")
        if alt_images:
            fields["image_urls"] = [img.get("src", "") for img in alt_images if img.get("src")]

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
            price_whole = item.select_one(".a-price-whole")
            rating_el = item.select_one(".a-icon-alt")
            review_el = item.select_one(".a-size-base.s-underline-text")
            img_el = item.select_one("img.s-image")

            items.append({
                "asin": asin,
                "title": title_el.text.strip() if title_el else "",
                "price": price_whole.text.strip() if price_whole else "",
                "rating": float(rating_el.text.split()[0]) if rating_el else None,
                "review_count": int(review_el.text.replace(",", "")) if review_el else None,
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
        from app.core.vision import extract_text_from_images

        # Collect image URLs: main + A+ images
        urls = []
        main = result.extracted_fields.get("main_image")
        if main:
            urls.append(main)

        # A+ images — extract from aplus_content
        aplus = result.extracted_fields.get("aplus_content", [])
        if isinstance(aplus, list):
            for block in aplus:
                if isinstance(block, str) and block.startswith("http"):
                    urls.append(block)

        # Also check image_urls
        extra = result.extracted_fields.get("image_urls", [])
        if isinstance(extra, list):
            urls.extend([u for u in extra if isinstance(u, str) and u.startswith("http")])

        if not urls:
            return

        try:
            ocr_results = await extract_text_from_images(urls[:4])  # max 4 to stay fast
            if ocr_results:
                result.extracted_fields["ocr_image_texts"] = {
                    url: text for url, text in ocr_results.items() if text
                }
        except Exception:
            pass

    def _extract_asin(self, url: str) -> str | None:
        import re
        match = re.search(r"/dp/([A-Z0-9]{10})", url)
        return match.group(1) if match else None
