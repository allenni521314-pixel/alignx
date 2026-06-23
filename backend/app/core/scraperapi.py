"""ScraperAPI provider — Amazon product and search capture."""

import json
import httpx
from app.config import get_settings
from app.core.capture import CaptureProvider, CaptureResult

settings = get_settings()

BASE = "https://api.scraperapi.com"


class ScraperAPIProvider:
    """Captures Amazon data via ScraperAPI structured/async endpoints."""

    def __init__(self) -> None:
        self.key = settings.scraperapi_key
        self.client = httpx.AsyncClient(timeout=60.0)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.key}"}

    # ── Product page by ASIN ──────────────────────────

    async def capture_product_by_asin(
        self, asin: str, marketplace: str = "amazon.com"
    ) -> CaptureResult:
        """POST /structured with product type."""
        try:
            resp = await self.client.post(
                f"{BASE}/structured",
                json={
                    "api_key": self.key,
                    "url": f"https://www.{marketplace}/dp/{asin}",
                    "type": "product",
                    "country_code": self._marketplace_to_country(marketplace),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse_product_response(data, asin)
        except Exception as e:
            return CaptureResult(
                capture_status="failed",
                capture_provider="scraperapi",
                error_message=str(e),
            )

    async def capture_product_by_url(
        self, url: str, marketplace: str = "amazon.com"
    ) -> CaptureResult:
        """Extract ASIN from URL, then delegate to ASIN capture."""
        asin = self._extract_asin(url)
        if not asin:
            return CaptureResult(
                capture_status="failed",
                capture_provider="scraperapi",
                error_message=f"Could not extract ASIN from URL: {url}",
            )
        return await self.capture_product_by_asin(asin, marketplace)

    # ── Top 20 by keyword ─────────────────────────────

    async def capture_top20_by_keyword(
        self, keyword: str, marketplace: str = "amazon.com"
    ) -> CaptureResult:
        """POST /structured with search type."""
        try:
            resp = await self.client.post(
                f"{BASE}/structured",
                json={
                    "api_key": self.key,
                    "url": f"https://www.{marketplace}/s?k={httpx.QueryParams({'k': keyword})['k']}",
                    "type": "search",
                    "country_code": self._marketplace_to_country(marketplace),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse_search_response(data, keyword)
        except Exception as e:
            return CaptureResult(
                capture_status="failed",
                capture_provider="scraperapi",
                error_message=str(e),
            )

    # ── Parse helpers ─────────────────────────────────

    def _parse_product_response(self, data: dict, asin: str) -> CaptureResult:
        """Extract listing fields from ScraperAPI structured product response."""
        fields = {}
        missing = []

        product = data.get("product", data)

        # Title
        title = product.get("title") or product.get("name")
        if title:
            fields["title"] = str(title)
        else:
            missing.append("title")

        # Price
        price_obj = product.get("price") or product.get("buying_options", [{}])[0].get("price")
        if price_obj:
            fields["price"] = str(price_obj.get("value") or price_obj)
            fields["price_value"] = price_obj.get("value") if isinstance(price_obj.get("value"), (int, float)) else None
            fields["currency"] = price_obj.get("currency", "USD")
        else:
            missing.append("price")

        # Rating & reviews
        rating = product.get("rating") or product.get("star_rating")
        if rating:
            fields["rating"] = float(rating)
        else:
            missing.append("rating")

        reviews = product.get("reviews_count") or product.get("total_reviews") or product.get("reviews", {}).get("total")
        if reviews:
            fields["review_count"] = int(reviews)
        else:
            missing.append("review_count")

        # Bought in past month
        bipm = product.get("bought_in_past_month") or product.get("sales_volume")
        if bipm:
            fields["bought_in_past_month_raw"] = str(bipm)
            fields["bought_in_past_month_value"] = self._parse_numeric(bipm)

        # Images
        main_img = product.get("main_image") or product.get("image")
        if main_img:
            fields["main_image"] = str(main_img)

        images = product.get("images") or product.get("image_urls") or product.get("gallery", [])
        if images:
            fields["image_urls"] = [str(img) for img in images] if isinstance(images, list) else [str(images)]

        if not fields.get("main_image") and not fields.get("image_urls"):
            missing.append("images")

        # Bullet points
        bullets = product.get("bullet_points") or product.get("feature_bullets") or product.get("description")
        if bullets:
            fields["bullet_points"] = (
                [str(b) for b in bullets] if isinstance(bullets, list) else [str(bullets)]
            )
        else:
            missing.append("bullet_points")

        # A+ content
        aplus = product.get("aplus_content") or product.get("a_plus_content") or product.get("description")
        if aplus:
            fields["aplus_content"] = aplus if isinstance(aplus, list) else [aplus]

        # Product details table
        details = product.get("product_details") or product.get("product_information") or product.get("specifications")
        if details:
            fields["product_details"] = details

        # Availability
        availability = product.get("availability") or product.get("stock")
        if availability:
            fields["availability"] = str(availability)

        # First available date
        fad = product.get("first_available") or product.get("date_first_available")
        if fad:
            fields["first_available_date"] = str(fad)

        completeness = 1.0 - (len(missing) / max(len(fields) + len(missing), 1))

        return CaptureResult(
            raw_response=data,
            extracted_fields=fields,
            missing_fields=missing,
            capture_status="partial" if missing else "success",
            capture_provider="scraperapi",
            data_completeness_score=round(completeness, 2),
        )

    def _parse_search_response(self, data: dict, keyword: str) -> CaptureResult:
        """Extract top-20 ASINs from ScraperAPI structured search response."""
        results = data.get("results", data.get("products", []))
        items = []

        for item in results[:20]:
            asin = item.get("asin") or item.get("id")
            if not asin:
                continue

            items.append({
                "asin": str(asin),
                "title": str(item.get("title") or item.get("name", "")),
                "price": str(item.get("price", {}).get("value") if isinstance(item.get("price"), dict) else item.get("price", "")),
                "rating": float(item.get("rating") or item.get("star_rating", 0)) or None,
                "review_count": int(item.get("reviews_count") or item.get("total_reviews", 0)) or None,
                "image": str(item.get("image") or item.get("main_image", "")),
                "bought_in_past_month": str(item.get("bought_in_past_month") or item.get("sales_volume", "")),
                "sponsored": bool(item.get("sponsored") or item.get("is_sponsored", False)),
            })

        return CaptureResult(
            raw_response=data,
            extracted_fields={"keyword": keyword, "results": items, "total": len(items)},
            capture_status="success" if items else "partial",
            capture_provider="scraperapi",
            data_completeness_score=1.0 if items else 0.0,
        )

    # ── Helpers ───────────────────────────────────────

    def _extract_asin(self, url: str) -> str | None:
        """Extract ASIN from an Amazon URL."""
        import re
        match = re.search(r"/dp/([A-Z0-9]{10})", url)
        if match:
            return match.group(1)
        match = re.search(r"/product/([A-Z0-9]{10})", url)
        if match:
            return match.group(1)
        return None

    def _marketplace_to_country(self, marketplace: str) -> str:
        return {
            "amazon.com": "us",
            "amazon.co.uk": "uk",
            "amazon.de": "de",
            "amazon.fr": "fr",
            "amazon.co.jp": "jp",
            "amazon.ca": "ca",
            "amazon.it": "it",
            "amazon.es": "es",
            "amazon.com.mx": "mx",
            "amazon.in": "in",
        }.get(marketplace, "us")

    @staticmethod
    def _parse_numeric(text: str) -> int | None:
        """Extract first number from a string like '10K+ bought'."""
        import re
        if not text:
            return None
        text = str(text).lower().replace(",", "")
        match = re.search(r"(\d+(?:\.\d+)?)\s*k", text)
        if match:
            return int(float(match.group(1)) * 1000)
        match = re.search(r"(\d+(?:\.\d+)?)\s*m", text)
        if match:
            return int(float(match.group(1)) * 1000000)
        match = re.search(r"(\d+)", text)
        if match:
            return int(match.group(1))
        return None
