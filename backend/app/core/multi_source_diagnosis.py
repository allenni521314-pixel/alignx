from __future__ import annotations

"""Multi-source diagnosis engine — combines ad data, listing diagnosis, and
TOP20 market data to classify problems into 5 dimensions.

Integrates with, but does not modify, the existing ListingDiagnosisValidationEngine.
"""

from typing import Any

from app.core.listing_diagnosis_validation import (
    FunnelDiagnosisEngine,
    ListingDiagnosisValidationEngine,
    _bounded_int,
)


class MultiSourceDiagnosisEngine:
    """Classify seller problems into 5 dimensions using 3 data sources."""

    def diagnose(
        self,
        *,
        asin: str,
        marketplace: str,
        ad_metrics: dict[str, Any] | None = None,
        listing_data: dict[str, Any] | None = None,
        ai_result: dict[str, Any] | None = None,
        top20_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ad = ad_metrics or {}
        top20 = top20_context or {}
        ai = ai_result or {}

        # ── Run listing diagnosis if we have listing data ──
        listing_diag = None
        if listing_data:
            listing_diag = ListingDiagnosisValidationEngine().analyze(
                asin=asin,
                marketplace=marketplace,
                listing_data=listing_data,
                ai_result=ai,
                ad_metrics=ad,
            )

        # ── 5-dimension classification ──
        dimensions = self._classify(ad, listing_diag, top20)

        # ── Determine primary problem ──
        scored = sorted(dimensions, key=lambda d: d["confidence"], reverse=True)
        primary = scored[0]

        # ── Action mapping ──
        actions = self._build_actions(primary, listing_diag, ad)

        return {
            "asin": asin,
            "diagnosis_type": "data_calibrated_diagnosis" if ad else "inference_only",
            "primary_problem": primary["dimension"],
            "primary_confidence": primary["confidence"],
            "primary_evidence": primary["evidence"],
            "dimensions": dimensions,
            "listing_diagnosis": listing_diag,
            "top_actions": actions,
            "system_can_fix": [a for a in actions if a.get("system_capable")],
            "human_required": [a for a in actions if not a.get("system_capable")],
        }

    def _classify(
        self,
        ad: dict[str, Any],
        listing_diag: dict[str, Any] | None,
        top20: dict[str, Any],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        # ── 1. Listing 问题 ──
        listing_conf, listing_evidence = self._listing_score(listing_diag)
        results.append({
            "dimension": "listing",
            "label": "Listing 问题",
            "confidence": listing_conf,
            "evidence": listing_evidence,
            "system_capable": True,
        })

        # ── 2. 广告错配 ──
        ad_conf, ad_evidence = self._ad_mismatch_score(ad, listing_diag)
        results.append({
            "dimension": "ad_mismatch",
            "label": "广告错配",
            "confidence": ad_conf,
            "evidence": ad_evidence,
            "system_capable": True,
        })

        # ── 3. 产品问题 ──
        product_conf, product_evidence = self._product_score(ad, listing_diag)
        results.append({
            "dimension": "product",
            "label": "产品问题",
            "confidence": product_conf,
            "evidence": product_evidence,
            "system_capable": False,
        })

        # ── 4. 价格问题 ──
        price_conf, price_evidence = self._price_score(ad, top20, listing_diag)
        results.append({
            "dimension": "price",
            "label": "价格问题",
            "confidence": price_conf,
            "evidence": price_evidence,
            "system_capable": False,
        })

        # ── 5. 市场行情 ──
        market_conf, market_evidence = self._market_score(ad, top20)
        results.append({
            "dimension": "market",
            "label": "市场行情",
            "confidence": market_conf,
            "evidence": market_evidence,
            "system_capable": False,
        })

        return results

    # ── Individual scorers ──

    def _listing_score(self, listing_diag: dict[str, Any] | None) -> tuple[int, str]:
        if not listing_diag:
            return 0, "暂无 Listing 诊断数据。"
        health = listing_diag.get("overall_health_score", 100)
        primary = listing_diag.get("primary_bottleneck", "")
        rule = listing_diag.get("rule_check", {})
        reasons: list[str] = []

        if health < 50:
            reasons.append(f"Listing 健康分仅 {health}，多处严重缺失或违规。")
        elif health < 70:
            reasons.append(f"Listing 健康分 {health}，存在弱覆盖或区位错配。")
        else:
            reasons.append(f"Listing 健康分 {health}，整体覆盖良好。")

        if rule.get("rule_status") == "block":
            reasons.append(f"平台规则禁止：{', '.join(rule.get('blocked_reasons', []))}")
        if rule.get("warnings"):
            reasons.append(f"规则警告：{', '.join(rule.get('warnings', [])[:3])}")

        conf = max(0, 100 - health)
        return _bounded_int(conf), " ".join(reasons) if reasons else "暂无明确 Listing 问题。"

    def _ad_mismatch_score(self, ad: dict[str, Any], listing_diag: dict[str, Any] | None) -> tuple[int, str]:
        if not ad:
            return 0, "暂无广告数据。"
        impressions = _num(ad.get("impressions"))
        ctr = _num(ad.get("ctr"))
        cvr = _num(ad.get("cvr"))
        acos = _num(ad.get("acos"))
        cpc = _num(ad.get("cpc"))
        reasons: list[str] = []
        score = 0

        # High impressions + low CTR → keywords not matching listing
        if impressions is not None and impressions > 5000 and ctr is not None and ctr < 0.003:
            reasons.append(f"曝光 {impressions:.0f} 但 CTR 仅 {ctr*100:.2f}%，搜索词与 Listing 不匹配。")
            score += 40
        # High CTR + low CVR → landing page mismatch
        if ctr is not None and ctr > 0.005 and cvr is not None and cvr < 0.03:
            reasons.append(f"CTR {ctr*100:.2f}% 正常但 CVR 仅 {cvr*100:.2f}%，广告位与承接页不匹配。")
            score += 35
        # High ACOS → overspending
        if acos is not None and acos > 0.40:
            reasons.append(f"ACOS {acos*100:.0f}% 过高，广告花费效率低。")
            score += 25
        # High CPC
        if cpc is not None and cpc > 1.5:
            reasons.append(f"CPC ${cpc:.2f} 偏高，关键词竞價激烈或相关性低。")
            score += 20

        if not reasons:
            reasons.append("广告指标在正常范围。")

        return _bounded_int(score), " ".join(reasons)

    def _product_score(self, ad: dict[str, Any], listing_diag: dict[str, Any] | None) -> tuple[int, str]:
        if not ad:
            return 0, "暂无销售数据，无法判断产品力。"
        cvr = _num(ad.get("cvr"))
        orders = _num(ad.get("orders"))
        reasons: list[str] = []
        score = 0

        # Low CVR despite good listing → product issue
        if listing_diag and listing_diag.get("overall_health_score", 0) > 70:
            if cvr is not None and cvr < 0.03:
                reasons.append("Listing 覆盖良好但 CVR 仍低，可能是产品不受欢迎。")
                score += 50
        if orders is not None and orders < 5:
            reasons.append("月订单量极低，需求存疑。")
            score += 30

        if not reasons:
            reasons.append("暂无明确产品问题信号。")
        return _bounded_int(score), " ".join(reasons)

    def _price_score(self, ad: dict[str, Any], top20: dict[str, Any], listing_diag: dict[str, Any] | None) -> tuple[int, str]:
        your_price = _num(ad.get("price"))
        top20_avg = _num(top20.get("avg_price"))
        reasons: list[str] = []
        score = 0

        if your_price is not None and top20_avg is not None and top20_avg > 0:
            ratio = your_price / top20_avg
            if ratio > 1.5:
                reasons.append(f"售价 ${your_price:.2f} 高于 TOP20 均价 ${top20_avg:.2f} 的 {ratio:.0%}。")
                score += 70
            elif ratio > 1.2:
                reasons.append(f"售价 ${your_price:.2f} 高于 TOP20 均价 ${top20_avg:.2f} 的 {ratio:.0%}。")
                score += 40
            else:
                reasons.append(f"售价 ${your_price:.2f} 与 TOP20 均价 ${top20_avg:.2f} 接近。")
        elif your_price is not None:
            reasons.append(f"当前售价 ${your_price:.2f}，暂无 TOP20 价格对照。")
        else:
            reasons.append("暂无价格数据。")

        return _bounded_int(score), " ".join(reasons)

    def _market_score(self, ad: dict[str, Any], top20: dict[str, Any]) -> tuple[int, str]:
        sample_count = top20.get("top20_sample_count", 0)
        bsr_trend = top20.get("bsr_trend", "")
        reasons: list[str] = []
        score = 0

        if bsr_trend == "declining":
            reasons.append("同类目 BSR 整体下滑，市场在萎缩。")
            score += 60
        elif bsr_trend == "rising":
            reasons.append("同类目 BSR 呈上升趋势。")
        elif sample_count > 0:
            reasons.append(f"TOP20 样本 {sample_count} 个，BSR 趋势平稳。")
        else:
            reasons.append("暂无市场行情数据。")

        return _bounded_int(score), " ".join(reasons)

    def _build_actions(
        self,
        primary: dict[str, Any],
        listing_diag: dict[str, Any] | None,
        ad: dict[str, Any],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        dim = primary["dimension"]

        if dim == "listing" and listing_diag:
            top = listing_diag.get("top_actions", [])
            for t in top[:2]:
                actions.append({
                    "priority": t.get("priority", 1),
                    "action": t.get("action", "优化 Listing"),
                    "target": t.get("target_position", ""),
                    "system_capable": True,
                    "route": "/conversion-diagnosis",
                })
        elif dim == "ad_mismatch":
            actions.append({
                "priority": 1,
                "action": "检查广告搜索词与 Listing 关键词匹配度",
                "target": "search_terms",
                "system_capable": True,
                "route": "/traffic-strategy",
            })
            actions.append({
                "priority": 2,
                "action": "降低无效关键词出价，增加精准长尾词",
                "target": "keyword_bid",
                "system_capable": True,
                "route": "/traffic-strategy",
            })
        elif dim == "price":
            actions.append({
                "priority": 1,
                "action": "对比竞品价格，考虑促销或降价测试",
                "target": "price",
                "system_capable": False,
            })
        elif dim == "product":
            actions.append({
                "priority": 1,
                "action": "检查差评内容，确认产品是否存在功能缺陷",
                "target": "product_quality",
                "system_capable": False,
            })
        elif dim == "market":
            actions.append({
                "priority": 1,
                "action": "市场行情走低，需人工判断是否继续投入",
                "target": "market",
                "system_capable": False,
            })

        if not actions:
            actions.append({
                "priority": 1,
                "action": "数据不足，请先上传广告报表或补充 Listing 数据",
                "system_capable": False,
            })

        return actions


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
