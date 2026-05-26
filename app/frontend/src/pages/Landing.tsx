import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight,
  BarChart3,
  Check,
  ClipboardCheck,
  Layers3,
  Megaphone,
  RotateCcw,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AlignXLogo } from "@/components/AlignXLogo";

const valueCards = [
  {
    title: "选品决策",
    desc: "判断 ASIN 是否值得进入机会池",
    icon: Layers3,
  },
  {
    title: "Listing诊断",
    desc: "识别标题、五点、图片、A+与评论需求的错配",
    icon: ClipboardCheck,
  },
  {
    title: "广告验证",
    desc: "用CTR、CVR、ACOS验证诊断假设是否成立",
    icon: Megaphone,
  },
  {
    title: "数据回流",
    desc: "把命中和未命中的假设沉淀为下一轮动作",
    icon: RotateCcw,
  },
];

const plans = [
  { name: "免费试用", price: "0 元", desc: "体验单品基础流程" },
  { name: "轻量版", price: "199 元/月", desc: "适合单店铺小规模测试" },
  { name: "专业版", price: "699 元/月", desc: "完整广告验证和复盘闭环", highlight: true },
  { name: "团队版", price: "1999 元/月", desc: "多账号、多店铺、批量 ASIN" },
];

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-white text-gray-900">
      <nav className="sticky top-0 z-40 bg-white/90 backdrop-blur border-b border-gray-100">
        <div className="h-16 max-w-7xl mx-auto px-5 sm:px-8 flex items-center justify-between">
          <AlignXLogo showWordmark markClassName="h-9 w-9" wordmarkClassName="text-xl" />
          <div className="hidden md:flex items-center gap-7 text-sm text-gray-500">
            <a href="#capabilities" className="hover:text-gray-900">产品能力</a>
            <a href="#pricing" className="hover:text-gray-900">定价</a>
            <button onClick={() => navigate("/login")} className="hover:text-gray-900">登录</button>
          </div>
          <Button onClick={() => navigate("/register")} className="bg-brand-600 hover:bg-brand-500 text-white">
            免费试用
          </Button>
        </div>
      </nav>

      <main>
        <section className="px-5 sm:px-8 py-16 sm:py-24 max-w-7xl mx-auto">
          <Badge className="mb-6 bg-brand-50 text-brand-700 border-brand-200">
            亚马逊商品转化决策系统
          </Badge>
          <h1 className="text-4xl sm:text-6xl font-bold tracking-tight max-w-4xl">
            AlignX 亚马逊商品转化决策系统
          </h1>
          <p className="text-gray-500 text-lg mt-6 max-w-3xl leading-relaxed">
            从ASIN和Listing诊断提出假设，用广告数据验证，再把命中结果回流到下一轮优化，帮助卖家持续逼近真实转化原因。
          </p>
          <div className="flex flex-col sm:flex-row gap-3 mt-8">
            <Button onClick={() => navigate("/register")} size="lg" className="bg-brand-600 hover:bg-brand-500 text-white">
              免费试用
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <Button onClick={() => navigate("/login")} size="lg" variant="outline">
              登录工作台
            </Button>
          </div>
        </section>

        <section id="capabilities" className="px-5 sm:px-8 pb-16 max-w-7xl mx-auto">
          <div className="mb-6">
            <h2 className="text-2xl font-bold">核心价值</h2>
            <p className="text-sm text-gray-500 mt-1">把 AI 判断放进标准化业务流程，而不是让卖家猜模型结论。</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {valueCards.map((item) => (
              <Card key={item.title} className="p-5 border-gray-200 bg-white">
                <item.icon className="w-5 h-5 text-brand-600 mb-4" />
                <h3 className="font-semibold text-gray-900">{item.title}</h3>
                <p className="text-sm text-gray-500 mt-2 leading-relaxed">{item.desc}</p>
              </Card>
            ))}
          </div>
        </section>

        <section className="px-5 sm:px-8 pb-16 max-w-7xl mx-auto">
          <Card className="p-6 border-gray-200 bg-gray-50">
            <h2 className="text-2xl font-bold mb-5">工作流程</h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-6 gap-3">
              {["ASIN选品", "上新检测", "本品诊断", "广告验证", "数据回流", "下一轮优化"].map((step, index) => (
                <div key={step} className="flex items-center gap-3 bg-white border border-gray-200 rounded-lg p-4">
                  <span className="w-7 h-7 rounded-full bg-brand-600 text-white text-xs font-bold flex items-center justify-center">
                    {index + 1}
                  </span>
                  <span className="font-medium text-sm">{step}</span>
                </div>
              ))}
            </div>
          </Card>
        </section>

        <section id="pricing" className="px-5 sm:px-8 pb-20 max-w-7xl mx-auto">
          <div className="mb-6">
            <h2 className="text-2xl font-bold">套餐入口</h2>
            <p className="text-sm text-gray-500 mt-1">先试用，再按 ASIN、Listing、广告验证和复盘额度升级。</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {plans.map((plan) => (
              <Card
                key={plan.name}
                className={`p-5 border-gray-200 bg-white ${plan.highlight ? "ring-2 ring-brand-500" : ""}`}
              >
                {plan.highlight && (
                  <Badge className="mb-3 bg-brand-50 text-brand-700 border-brand-200">推荐</Badge>
                )}
                <h3 className="font-semibold text-gray-900">{plan.name}</h3>
                <p className="text-2xl font-bold mt-3">{plan.price}</p>
                <p className="text-sm text-gray-500 mt-2 min-h-[40px]">{plan.desc}</p>
                <div className="mt-4 flex items-center gap-2 text-xs text-gray-500">
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  按月度额度控制
                </div>
                <Button
                  onClick={() => navigate("/pricing")}
                  variant={plan.highlight ? "default" : "outline"}
                  className={`w-full mt-5 ${plan.highlight ? "bg-brand-600 hover:bg-brand-500 text-white" : ""}`}
                >
                  查看套餐
                </Button>
              </Card>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
