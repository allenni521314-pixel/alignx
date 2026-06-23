"""Proposition seeder — populate the 49 propositions (7 categories × 7 each)."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import PropositionCategory, Proposition
from app.core.proposition_engine import PROPOSITION_CATEGORIES, PROPOSITIONS_PER_CATEGORY, build_proposition_code

# 49 propositions indexed by P01-001 through P07-007
PROPOSITIONS = {
    # ── P01: 流量命题库 ──
    "P01-001": {"name": "CTR 低于类目均值", "definition": "广告或自然搜索结果点击率低于类目平均水平", "controlled_variable": "主图 / 标题"},
    "P01-002": {"name": "关键词排名下降", "definition": "核心关键词自然排名持续下降", "controlled_variable": "Listing 相关性和销量"},
    "P01-003": {"name": "广告曝光不足", "definition": "广告展示量低于预期", "controlled_variable": "出价 / 预算"},
    "P01-004": {"name": "自然流量占比低", "definition": "自然流量占总流量比例过低", "controlled_variable": "自然排名优化"},
    "P01-005": {"name": "高流量低转化", "definition": "流量充足但转化率低", "controlled_variable": "Listing 内容"},
    "P01-006": {"name": "关联流量缺失", "definition": "缺少竞品关联流量和推荐位", "controlled_variable": "广告定位策略"},
    "P01-007": {"name": "流量来源单一", "definition": "过度依赖单一流量渠道", "controlled_variable": "多渠道引流"},

    # ── P02: 主图命题库 ──
    "P02-001": {"name": "主图差异化不足", "definition": "搜索结果中主图与竞品区分度低", "controlled_variable": "主图设计"},
    "P02-002": {"name": "主图信息密度低", "definition": "主图未有效传递核心卖点", "controlled_variable": "主图内容"},
    "P02-003": {"name": "主图尺寸/比例问题", "definition": "主图不符合 Amazon 最佳实践", "controlled_variable": "主图尺寸"},
    "P02-004": {"name": "主图场景缺失", "definition": "缺少使用场景展示", "controlled_variable": "场景图"},
    "P02-005": {"name": "主图移动端适配差", "description": "移动端显示效果不佳", "controlled_variable": "移动端优化"},
    "P02-006": {"name": "主图违反平台规则", "definition": "主图包含禁止元素", "controlled_variable": "合规"},
    "P02-007": {"name": "主图 A/B 测试未做", "definition": "未对主图进行过 A/B 测试", "controlled_variable": "主图版本"},

    # ── P03: 副图承接命题库 ──
    "P03-001": {"name": "副图信息结构混乱", "definition": "副图未按 Buyer Journey 组织", "controlled_variable": "图片顺序和内容"},
    "P03-002": {"name": "副图缺少尺寸对比", "definition": "缺少产品尺寸参照", "controlled_variable": "尺寸展示图"},
    "P03-003": {"name": "副图缺少功能演示", "definition": "未展示产品核心功能", "controlled_variable": "功能图"},
    "P03-004": {"name": "副图缺少信任背书", "definition": "缺少认证/质保/测试等信任元素", "controlled_variable": "信任元素"},
    "P03-005": {"name": "副图数量不足", "definition": "副图少于 5 张", "controlled_variable": "图片数量"},
    "P03-006": {"name": "副图质量低", "definition": "图片分辨率/光线/构图不佳", "controlled_variable": "图片质量"},
    "P03-007": {"name": "视频缺失", "definition": "未上传产品视频", "controlled_variable": "视频内容"},

    # ── P04: 价格带命题库 ──
    "P04-001": {"name": "定价高于竞品均值", "definition": "价格高于同类 Top20 均价", "controlled_variable": "售价"},
    "P04-002": {"name": "定价低于合理利润线", "definition": "价格过低导致亏损", "controlled_variable": "售价"},
    "P04-003": {"name": "Coupon 使用策略不当", "definition": "Coupon 力度或时机不合理", "controlled_variable": "Coupon 设置"},
    "P04-004": {"name": "价格感知不匹配", "definition": "Listing 呈现的价值感与价格不匹配", "controlled_variable": "Listing 呈现"},
    "P04-005": {"name": "促销节奏混乱", "definition": "折扣频率和幅度不合理", "controlled_variable": "促销策略"},
    "P04-006": {"name": "捆绑定价未利用", "definition": "未使用 Variation/Bundle 定价策略", "controlled_variable": "捆绑定价"},
    "P04-007": {"name": "竞争对手价格战", "definition": "竞品频繁降价", "controlled_variable": "差异化策略"},

    # ── P05: 信任命题库 ──
    "P05-001": {"name": "评论数量不足", "definition": "评论数不足以建立信任", "controlled_variable": "评论获取策略"},
    "P05-002": {"name": "评分低于 4.0", "definition": "星级评分处于危险区间", "controlled_variable": "产品质量 / 客服"},
    "P05-003": {"name": "差评模式集中", "definition": "差评集中在特定问题上", "controlled_variable": "产品改进"},
    "P05-004": {"name": "无 Vine / Early Reviewer", "definition": "未使用官方评论获取通道", "controlled_variable": "Vine 计划"},
    "P05-005": {"name": "品牌信号弱", "definition": "品牌页面/A+ 内容等信任信号不足", "controlled_variable": "品牌建设"},
    "P05-006": {"name": "Q&A 数量少", "definition": "产品问答区活跃度低", "controlled_variable": "Q&A 运营"},
    "P05-007": {"name": "退货率高", "definition": "退货率高于类目均值", "controlled_variable": "产品描述准确性"},

    # ── P06: 买家语言命题库 ──
    "P06-001": {"name": "标题关键词堆砌", "definition": "标题可读性差，关键词堆砌", "controlled_variable": "标题写法"},
    "P06-002": {"name": "五点卖点不突出", "definition": "五点未突出买家关心的核心利益", "controlled_variable": "五点内容"},
    "P06-003": {"name": "A+ 文案说服力弱", "definition": "A+ 内容未有效推动转化", "controlled_variable": "A+ 文案"},
    "P06-004": {"name": "买家语言不匹配", "definition": "用词与目标买家搜索习惯不一致", "controlled_variable": "关键词和用语"},
    "P06-005": {"name": "卖点与差评不一致", "definition": "强调的卖点与差评反馈的矛盾", "controlled_variable": "卖点调整"},
    "P06-006": {"name": "缺少场景化描述", "definition": "未描写使用场景和效果", "controlled_variable": "场景文案"},
    "P06-007": {"name": "移动端阅读体验差", "definition": "文案在移动端断行/可读性不佳", "controlled_variable": "移动端优化"},

    # ── P07: 需求不成立命题库 ──
    "P07-001": {"name": "市场规模不足", "definition": "目标市场搜索量/需求量不足以支撑盈利", "controlled_variable": "市场选择"},
    "P07-002": {"name": "用户付费意愿低", "definition": "目标用户不愿为产品支付合理价格", "controlled_variable": "定价/产品定位"},
    "P07-003": {"name": "产品差异化不存在", "definition": "产品与竞品无实质差异", "controlled_variable": "产品改进/差异化"},
    "P07-004": {"name": "供应链不可持续", "definition": "生产成本/物流导致无法盈利", "controlled_variable": "供应链优化"},
    "P07-005": {"name": "合规风险过高", "definition": "产品面临专利/认证/平台政策风险", "controlled_variable": "合规审查"},
    "P07-006": {"name": "季节性需求陷阱", "definition": "需求集中在短季节周期", "controlled_variable": "品类选择"},
    "P07-007": {"name": "竞品壁垒过高", "definition": "头部竞品已形成不可突破的壁垒", "controlled_variable": "市场选择/切入角度"},
}


async def seed_propositions(db: AsyncSession) -> dict:
    """Ensure all 7 categories and 49 propositions exist. Idempotent."""
    created_cats = 0
    created_props = 0

    # Categories
    for code, info in PROPOSITION_CATEGORIES.items():
        existing = await db.execute(
            select(PropositionCategory).where(PropositionCategory.category_code == code)
        )
        if not existing.scalar_one_or_none():
            db.add(PropositionCategory(
                category_code=code,
                category_name=info["name"],
                description=info["description"],
            ))
            created_cats += 1

    await db.flush()

    # Propositions
    for code, info in PROPOSITIONS.items():
        existing = await db.execute(
            select(Proposition).where(Proposition.proposition_code == code)
        )
        if not existing.scalar_one_or_none():
            cat_code = code[:3]  # P01, P02, etc.
            db.add(Proposition(
                proposition_code=code,
                category_code=cat_code,
                name=info["name"],
                definition=info.get("definition", ""),
                controlled_variable=info.get("controlled_variable", ""),
            ))
            created_props += 1

    await db.flush()
    return {"categories_created": created_cats, "propositions_created": created_props}
