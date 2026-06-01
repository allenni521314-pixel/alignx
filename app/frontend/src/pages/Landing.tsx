import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight,
  Check,
  ClipboardCheck,
  Layers3,
  Megaphone,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AlignXLogo } from "@/components/AlignXLogo";
import { FeedbackDialog } from "@/components/FeedbackDialog";
import { versionLabel } from "@/lib/version";

const valueCards = [
  {
    title: "是否值得做",
    desc: "看需求、竞争、利润和验证成本。",
    icon: Layers3,
  },
  {
    title: "先改哪里",
    desc: "定位标题、五点、图片和评论问题。",
    icon: ClipboardCheck,
  },
  {
    title: "验证什么",
    desc: "用广告数据验证判断。",
    icon: Megaphone,
  },
];

const plans = [
  { name: "免费试用", price: "0 元", desc: "验证一个ASIN的判断链路" },
  { name: "轻量版", price: "199 元/月", desc: "适合单店铺日常验证" },
  { name: "专业版", price: "699 元/月", desc: "包含诊断、广告和复盘闭环", highlight: true },
  { name: "团队版", price: "1999 元/月", desc: "适合多账号批量管理" },
];

export default function Landing() {
  const navigate = useNavigate();
  const workflowSteps = ["抓取真实数据", "拦截低置信机会", "定位转化卡点", "生成验证动作", "记录命中结果", "排下一轮优先级"];
  const decisionRows = [
    { label: "ASIN", input: "页面数据", output: "是否继续投入" },
    { label: "Listing", input: "内容与评论", output: "先处理的卡点" },
    { label: "广告", input: "验证数据", output: "下一轮动作" },
  ];

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-gray-950">
      <nav className="sticky top-0 z-40 border-b border-black/5 bg-[#f5f5f7]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-12 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <AlignXLogo showWordmark markClassName="h-8 w-8 rounded-lg" wordmarkClassName="text-lg" />
          <div className="hidden items-center gap-7 text-sm font-medium text-gray-500 md:flex">
            <a href="#capabilities" className="hover:text-gray-950">能力</a>
            <a href="#workflow" className="hover:text-gray-950">流程</a>
            <a href="#pricing" className="hover:text-gray-950">定价</a>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/login")} className="text-sm font-medium text-gray-500 hover:text-gray-950">
              登录
            </button>
            <Button onClick={() => navigate("/register")} className="h-8 rounded-full bg-brand-800 px-4 text-xs text-white hover:bg-brand-700">
              注册
            </Button>
          </div>
        </div>
      </nav>

      <main>
        <section className="mx-auto max-w-6xl px-4 pb-20 pt-16 sm:px-6 sm:pt-20 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <Badge className="mb-5 rounded-full border-brand-100 bg-white/80 px-3 py-1 text-brand-800 shadow-sm">
              亚马逊运营判断
            </Badge>
            <h1 className="text-4xl font-semibold leading-[1.04] tracking-tight text-gray-950 sm:text-5xl lg:text-6xl">
              判断产品，验证结果。
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-gray-600">
              判断ASIN值不值得做，Listing先改哪里，广告验证什么。
            </p>
            <Button onClick={() => navigate("/register")} size="lg" className="mt-7 h-10 rounded-full bg-brand-800 px-5 text-sm text-white hover:bg-brand-700">
              分析ASIN
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>

          <div className="mx-auto mt-16 max-w-5xl">
            <div className="overflow-hidden rounded-lg border border-black/5 bg-white shadow-[0_30px_90px_rgba(15,23,42,0.10)]">
              <div className="flex items-center justify-between border-b border-black/5 px-5 py-4 sm:px-6">
                <div>
                  <div className="text-sm font-semibold text-gray-950">核心判断链路</div>
                  <div className="mt-1 text-xs text-gray-500">ASIN / Listing / Ads</div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
                </div>
              </div>
              <div className="grid gap-0 lg:grid-cols-[1fr_0.78fr]">
                <div className="p-5 sm:p-6">
                  <div className="grid grid-cols-[0.8fr_1fr_1fr] gap-2 text-xs font-semibold text-gray-400">
                    <span>对象</span>
                    <span>输入</span>
                    <span>判断</span>
                  </div>
                  <div className="mt-3 overflow-hidden rounded-lg border border-black/5">
                    {decisionRows.map((row, index) => (
                      <div key={row.label} className="grid grid-cols-[0.8fr_1fr_1fr] items-center border-b border-black/5 bg-white last:border-b-0">
                        <div className="flex items-center gap-3 px-4 py-4">
                          <span className="text-[11px] font-semibold text-gold-700">{String(index + 1).padStart(2, "0")}</span>
                          <span className="text-sm font-semibold text-gray-950">{row.label}</span>
                        </div>
                        <div className="px-4 py-4 text-sm text-gray-500">{row.input}</div>
                        <div className="px-4 py-4 text-sm font-semibold text-brand-900">{row.output}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="border-t border-black/5 bg-[#f8f9f6] p-5 sm:p-6 lg:border-l lg:border-t-0">
                  <div className="text-sm font-semibold text-brand-900">判断输出</div>
                  <div className="mt-4 space-y-2">
                    {workflowSteps.slice(0, 4).map((step, index) => (
                      <div key={step} className="flex items-center justify-between rounded-md border border-brand-100 bg-white/80 px-3 py-2.5">
                        <span className="text-[11px] font-semibold text-gold-700">{String(index + 1).padStart(2, "0")}</span>
                        <span className="text-sm font-medium text-brand-950">{step}</span>
                      </div>
                    ))}
                    {workflowSteps.slice(4).map((step, index) => (
                      <div key={step} className="flex items-center justify-between rounded-md border border-brand-100 bg-white/80 px-3 py-2.5">
                        <span className="text-[11px] font-semibold text-gold-700">{String(index + 5).padStart(2, "0")}</span>
                        <span className="text-sm font-medium text-brand-950">{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="capabilities" className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">只回答三件事。</h2>
            <p className="mt-3 text-sm leading-6 text-gray-500">是否值得做，先改哪里，验证什么。</p>
          </div>
          <div className="mt-12 grid gap-px overflow-hidden rounded-lg border border-black/5 bg-black/5 md:grid-cols-3">
            {valueCards.map((item) => (
              <div key={item.title} className="bg-white p-6">
                <item.icon className="mb-7 h-5 w-5 text-brand-700" />
                <h3 className="text-base font-semibold text-gray-950">{item.title}</h3>
                <p className="mt-3 text-sm leading-6 text-gray-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="workflow" className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="grid gap-12 border-y border-black/5 py-16 lg:grid-cols-[0.32fr_1fr]">
            <div className="max-w-sm">
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">数据怎么流转</h2>
              <p className="mt-3 text-sm leading-6 text-gray-500">抓取、判断、验证、回流。</p>
            </div>
            <div className="grid gap-px overflow-hidden rounded-lg border border-black/5 bg-black/5 sm:grid-cols-2 lg:grid-cols-3">
              {workflowSteps.map((step, index) => (
                <div key={step} className="flex min-h-28 flex-col justify-between bg-white p-5">
                  <span className="text-xs font-semibold text-gold-700">{String(index + 1).padStart(2, "0")}</span>
                  <span className="text-sm font-semibold text-gray-950">{step}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="pricing" className="mx-auto max-w-6xl px-4 pb-24 pt-16 sm:px-6 lg:px-8">
          <div className="mb-10 text-center">
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">先测一个ASIN</h2>
            <p className="mt-3 text-sm text-gray-500">先看一次判断结果。</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`rounded-lg border bg-white p-5 shadow-sm ${plan.highlight ? "border-brand-300 ring-2 ring-brand-100" : "border-black/5"}`}
              >
                {plan.highlight && (
                  <Badge className="mb-3 rounded-full border-brand-200 bg-brand-50 text-brand-700">推荐</Badge>
                )}
                <h3 className="font-semibold text-gray-950">{plan.name}</h3>
                <p className="mt-3 text-2xl font-semibold">{plan.price}</p>
                <p className="mt-2 min-h-[40px] text-sm leading-6 text-gray-500">{plan.desc}</p>
                <div className="mt-4 flex items-center gap-2 text-xs font-medium text-gray-500">
                  <Check className="h-3.5 w-3.5 text-emerald-600" />
                  月度额度
                </div>
                <Button
                  onClick={() => navigate("/pricing")}
                  variant={plan.highlight ? "default" : "outline"}
                  className={`mt-5 h-10 w-full rounded-full ${plan.highlight ? "bg-brand-800 text-white hover:bg-brand-700" : "bg-white"}`}
                >
                  查看
                </Button>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-black/5 bg-white/50 py-6">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 text-xs text-gray-400 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <span>© 2026 深圳灵曦智感科技有限公司. {versionLabel()}</span>
          <div className="flex items-center gap-4">
            <button onClick={() => navigate("/terms")} className="hover:text-gray-700">用户协议</button>
            <button onClick={() => navigate("/privacy")} className="hover:text-gray-700">隐私政策</button>
            <FeedbackDialog variant="ghost" triggerClassName="h-auto p-0 text-xs text-gray-400 hover:text-gray-700" />
          </div>
        </div>
      </footer>
    </div>
  );
}
