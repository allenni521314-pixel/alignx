import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight,
  Check,
  ClipboardCheck,
  Layers3,
  Megaphone,
  RotateCcw,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AlignXLogo } from "@/components/AlignXLogo";
import { FeedbackDialog } from "@/components/FeedbackDialog";
import { versionLabel } from "@/lib/version";

const valueCards = [
  {
    title: "选品判断",
    desc: "需求、竞争、利润、验证成本",
    icon: Layers3,
  },
  {
    title: "Listing优先级",
    desc: "标题、五点、图片、评论问题",
    icon: ClipboardCheck,
  },
  {
    title: "广告验证",
    desc: "CTR、CVR、ACOS、订单信号",
    icon: Megaphone,
  },
  {
    title: "复盘回流",
    desc: "命中结论、未命中原因、下一轮动作",
    icon: RotateCcw,
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
  const heroSignals = ["是否值得投", "先改哪里", "验证什么"];
  const decisionRows = [
    { label: "ASIN", input: "页面数据", output: "是否继续投入" },
    { label: "Listing", input: "内容与评论", output: "先处理的卡点" },
    { label: "广告", input: "验证数据", output: "下一轮动作" },
  ];

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-gray-950">
      <nav className="sticky top-0 z-40 border-b border-black/5 bg-[#f5f5f7]/85 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <AlignXLogo showWordmark markClassName="h-8 w-8 rounded-lg" wordmarkClassName="text-lg" />
          <div className="hidden items-center gap-1 rounded-full border border-black/5 bg-white/70 p-1 text-sm font-medium text-gray-500 shadow-sm md:flex">
            <a href="#capabilities" className="rounded-full px-4 py-2 hover:bg-gray-100 hover:text-gray-950">决策能力</a>
            <a href="#pricing" className="rounded-full px-4 py-2 hover:bg-gray-100 hover:text-gray-950">定价</a>
            <button onClick={() => navigate("/terms")} className="rounded-full px-4 py-2 hover:bg-gray-100 hover:text-gray-950">用户协议</button>
          </div>
          <Button onClick={() => navigate("/login")} className="h-9 rounded-full bg-brand-800 px-5 text-white hover:bg-brand-700">
            登录
          </Button>
        </div>
      </nav>

      <main>
        <section className="mx-auto grid min-h-[calc(100vh-56px)] max-w-7xl items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:px-8 lg:py-14">
          <div className="max-w-2xl">
            <Badge className="mb-5 rounded-full border-brand-200 bg-white px-3 py-1 text-brand-800 shadow-sm">
              亚马逊运营判断工具
            </Badge>
            <h1 className="max-w-3xl text-4xl font-semibold leading-[1.04] tracking-tight text-gray-950 sm:text-5xl xl:text-6xl">
              从ASIN判断到广告验证，形成一条决策链
            </h1>
            <p className="mt-6 max-w-xl text-base leading-8 text-gray-600">
              先判断产品是否值得投入，再定位Listing卡点，最后用广告数据验证判断是否成立。
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button onClick={() => navigate("/register")} size="lg" className="h-11 rounded-full bg-brand-800 px-6 text-white hover:bg-brand-700">
                分析一个ASIN
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
            <div className="mt-10 grid max-w-lg grid-cols-3 divide-x divide-black/5 rounded-lg border border-black/5 bg-white/70 shadow-sm">
              {heroSignals.map((signal, index) => (
                <div key={signal} className="p-4">
                  <div className="text-[11px] font-semibold text-gold-700">关注 {String(index + 1).padStart(2, "0")}</div>
                  <div className="mt-2 text-sm font-semibold text-gray-950">{signal}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="absolute -inset-6 rounded-[32px] bg-white/45 blur-3xl" aria-hidden="true" />
            <div className="relative overflow-hidden rounded-lg border border-black/5 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.10)]">
              <div className="flex items-center justify-between border-b border-black/5 px-5 py-4">
                <div>
                  <div className="text-sm font-semibold text-gray-950">核心判断链路</div>
                  <div className="mt-1 text-xs text-gray-500">从数据到动作</div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
                </div>
              </div>
              <div className="p-5">
                <div className="grid grid-cols-[0.9fr_1fr_1fr] gap-2 text-xs font-semibold text-gray-400">
                  <span>对象</span>
                  <span>输入</span>
                  <span>输出</span>
                </div>
                <div className="mt-3 overflow-hidden rounded-lg border border-black/5">
                  {decisionRows.map((row, index) => (
                    <div key={row.label} className="grid grid-cols-[0.9fr_1fr_1fr] items-center border-b border-black/5 bg-white last:border-b-0">
                      <div className="flex items-center gap-3 px-4 py-4">
                        <span className="text-[11px] font-semibold text-gold-700">{String(index + 1).padStart(2, "0")}</span>
                        <span className="text-sm font-semibold text-gray-950">{row.label}</span>
                      </div>
                      <div className="px-4 py-4 text-sm text-gray-500">{row.input}</div>
                      <div className="px-4 py-4 text-sm font-semibold text-brand-900">{row.output}</div>
                    </div>
                  ))}
                </div>

                <div className="mt-5 rounded-lg border border-brand-100 bg-brand-50/40 p-4">
                  <div className="mb-3 text-sm font-semibold text-brand-900">判断输出</div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {workflowSteps.slice(0, 4).map((step, index) => (
                      <div key={step} className="flex items-center justify-between rounded-md border border-brand-100 bg-white/80 px-3 py-2.5">
                        <span className="text-[11px] font-semibold text-gold-700">{String(index + 1).padStart(2, "0")}</span>
                        <span className="text-sm font-medium text-brand-950">{step}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
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

        <section id="capabilities" className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
          <div className="grid gap-6 border-y border-black/5 py-10 lg:grid-cols-[0.34fr_1fr]">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">解决三个日常判断</h2>
              <p className="mt-2 text-sm leading-6 text-gray-500">页面数据、Listing诊断和广告表现使用同一套判断标准。</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {valueCards.map((item) => (
                <div key={item.title} className="border-l border-black/10 pl-5">
                  <item.icon className="mb-4 h-5 w-5 text-brand-700" />
                  <h3 className="font-semibold text-gray-950">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-gray-500">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
          <div className="border border-black/5 bg-white p-5 shadow-sm">
            <h2 className="pb-5 text-2xl font-semibold tracking-tight">数据如何进入判断</h2>
            <div className="grid gap-px overflow-hidden border border-black/5 bg-black/5 sm:grid-cols-2 lg:grid-cols-6">
              {workflowSteps.map((step, index) => (
                <div key={step} className="flex min-h-24 flex-col justify-between bg-[#f8f8fa] p-4">
                  <span className="text-xs font-semibold text-gray-400">{String(index + 1).padStart(2, "0")}</span>
                  <span className="text-sm font-semibold text-gray-950">{step}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="pricing" className="mx-auto max-w-7xl px-4 pb-20 sm:px-6 lg:px-8">
          <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">先从一个ASIN开始验证</h2>
              <p className="mt-2 text-sm text-gray-500">从单品判断开始，查看选品、Listing和广告验证是否形成闭环。</p>
            </div>
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
                  按月度额度控制
                </div>
                <Button
                  onClick={() => navigate("/pricing")}
                  variant={plan.highlight ? "default" : "outline"}
                  className={`mt-5 h-10 w-full rounded-full ${plan.highlight ? "bg-brand-800 text-white hover:bg-brand-700" : "bg-white"}`}
                >
                  查看套餐
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
