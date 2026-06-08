from typing import Optional

from schemas.advertising_strategy import (
    AdPathItem,
    AdvertisingStrategyInput,
    AdvertisingStrategyOutput,
    BidStrategy,
    BudgetAllocationItem,
    CampaignMatrixItem,
    CurrentAdStatus,
    ExpectedOutcome,
    PlacementStrategyItem,
    ValidationGoal,
)


class AdvertisingStrategyEngine:
    def build_schema(self) -> AdvertisingStrategyOutput:
        return self.evaluate()

    @staticmethod
    def _health_grade(proof_score: float) -> str:
        if proof_score >= 80:
            return "A"
        if proof_score >= 65:
            return "B"
        if proof_score >= 45:
            return "C"
        if proof_score > 0:
            return "D"
        return "未设置"

    @staticmethod
    def _budget_amounts(level: str) -> list[tuple[str, str]]:
        if level == "高":
            return [("测试预算", "300"), ("验证预算", "500"), ("放量预算", "900"), ("防守预算", "300")]
        if level == "中":
            return [("测试预算", "150"), ("验证预算", "250"), ("放量预算", "450"), ("防守预算", "150")]
        if level == "低":
            return [("测试预算", "50"), ("验证预算", "100"), ("放量预算", "150"), ("防守预算", "50")]
        return [("测试预算", "未设置"), ("验证预算", "未设置"), ("放量预算", "未设置"), ("防守预算", "未设置")]

    @staticmethod
    def _recommended_path(stage: str, product_type: str) -> list[AdPathItem]:
        if stage == "新品":
            return [
                AdPathItem(channel="自动广告", ratio="30%"),
                AdPathItem(channel="精准关键词", ratio="20%"),
                AdPathItem(channel="场景关键词", ratio="20%"),
                AdPathItem(channel="竞品ASIN", ratio="30%"),
            ]
        if product_type == "标品":
            return [
                AdPathItem(channel="自动广告", ratio="15%"),
                AdPathItem(channel="精准关键词", ratio="35%"),
                AdPathItem(channel="场景关键词", ratio="15%"),
                AdPathItem(channel="竞品ASIN", ratio="35%"),
            ]
        return [
            AdPathItem(channel="自动广告", ratio="20%"),
            AdPathItem(channel="精准关键词", ratio="25%"),
            AdPathItem(channel="场景关键词", ratio="35%"),
            AdPathItem(channel="竞品ASIN", ratio="20%"),
        ]

    @staticmethod
    def _campaign_matrix(stage: str, product_type: str) -> list[CampaignMatrixItem]:
        grades = {
            "自动广告": "A" if stage == "新品" else "B",
            "精准匹配": "B" if stage == "新品" else "A",
            "词组匹配": "B",
            "广泛匹配": "C",
            "ASIN投放": "A" if product_type in {"标品", "半标品"} else "B",
            "品类投放": "C",
            "品牌广告": "C" if stage in {"新品", "成长"} else "B",
            "展示广告": "D" if stage == "新品" else "C",
        }
        return [CampaignMatrixItem(campaign_type=name, recommendation_grade=grade) for name, grade in grades.items()]

    @staticmethod
    def _placement_strategy(stage: str) -> list[PlacementStrategyItem]:
        if stage == "新品":
            values = [("首页顶部", "20%"), ("搜索中部", "30%"), ("搜索底部", "20%"), ("竞品详情页", "25%"), ("关联商品页", "5%")]
        else:
            values = [("首页顶部", "30%"), ("搜索中部", "25%"), ("搜索底部", "10%"), ("竞品详情页", "25%"), ("关联商品页", "10%")]
        return [PlacementStrategyItem(placement=name, ratio=ratio) for name, ratio in values]

    def evaluate(self, payload: Optional[AdvertisingStrategyInput] = None) -> AdvertisingStrategyOutput:
        stage = payload.product_stage if payload else "待录入"
        product_type = payload.product_type if payload else "待录入"
        budget_level = payload.budget_level if payload else "待录入"
        proof_score = float(payload.proof_score if payload else 0)
        budget_amounts = self._budget_amounts(budget_level)
        return AdvertisingStrategyOutput(
            current_ad_status=CurrentAdStatus(
                product_stage=stage,
                product_type=product_type,
                budget_level=budget_level,
                ad_health_grade=self._health_grade(proof_score),
            ),
            recommended_ad_path=self._recommended_path(stage, product_type),
            campaign_matrix=self._campaign_matrix(stage, product_type),
            placement_strategy=self._placement_strategy(stage),
            bid_strategy=BidStrategy(
                fixed_bid="B",
                dynamic_down="A",
                dynamic_up="C",
                dynamic_up_down="B",
                recommended="动态降低",
            ),
            budget_allocation=[
                BudgetAllocationItem(budget_type=name, amount=amount, ratio=ratio)
                for (name, amount), ratio in zip(budget_amounts, ["15%", "25%", "45%", "15%"])
            ],
            validation_goal=ValidationGoal(
                goal_type="Listing验证",
                ctr_target="0.35%",
                cvr_target="8%",
                acos_target="35%",
                roi_target="1.8",
                validation_period="7天",
            ),
            biggest_waste="广泛匹配浪费",
            next_best_action="增加竞品ASIN预算",
            expected_outcome=ExpectedOutcome(
                ctr_lift="10%",
                cvr_lift="8%",
                acos_improvement="5%",
                roi_improvement="10%",
            ),
        )


advertising_strategy_engine = AdvertisingStrategyEngine()
