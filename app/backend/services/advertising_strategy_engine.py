from schemas.advertising_strategy import (
    AdPathItem,
    AdvertisingStrategyInput,
    AdvertisingStrategyOutput,
    BudgetAllocationItem,
    CampaignMatrixItem,
    CurrentAdStatus,
    PlacementStrategyItem,
)


class AdvertisingStrategyEngine:
    def build_schema(self) -> AdvertisingStrategyOutput:
        return self.evaluate()

    def evaluate(self, payload: AdvertisingStrategyInput | None = None) -> AdvertisingStrategyOutput:
        return AdvertisingStrategyOutput(
            current_ad_status=CurrentAdStatus(
                product_stage=payload.product_stage if payload else "待录入",
                product_type=payload.product_type if payload else "待录入",
                budget_level=payload.budget_level if payload else "待录入",
                ad_health_grade="未设置",
            ),
            recommended_ad_path=[
                AdPathItem(channel="自动广告"),
                AdPathItem(channel="精准关键词"),
                AdPathItem(channel="场景关键词"),
                AdPathItem(channel="竞品ASIN"),
            ],
            campaign_matrix=[
                CampaignMatrixItem(campaign_type="自动广告"),
                CampaignMatrixItem(campaign_type="精准匹配"),
                CampaignMatrixItem(campaign_type="词组匹配"),
                CampaignMatrixItem(campaign_type="广泛匹配"),
                CampaignMatrixItem(campaign_type="ASIN投放"),
                CampaignMatrixItem(campaign_type="品类投放"),
                CampaignMatrixItem(campaign_type="品牌广告"),
                CampaignMatrixItem(campaign_type="展示广告"),
            ],
            placement_strategy=[
                PlacementStrategyItem(placement="首页顶部"),
                PlacementStrategyItem(placement="搜索中部"),
                PlacementStrategyItem(placement="搜索底部"),
                PlacementStrategyItem(placement="竞品详情页"),
                PlacementStrategyItem(placement="关联商品页"),
            ],
            budget_allocation=[
                BudgetAllocationItem(budget_type="测试预算"),
                BudgetAllocationItem(budget_type="验证预算"),
                BudgetAllocationItem(budget_type="放量预算"),
                BudgetAllocationItem(budget_type="防守预算"),
            ],
        )


advertising_strategy_engine = AdvertisingStrategyEngine()
