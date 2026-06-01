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
    title: "不再凭感觉选品",
    desc: "先看需求、竞争、利润和验证成本，低置信机会直接拦截。",
    icon: Layers3,
  },
  {
    title: "不再盲改Listing",
    desc: "把标题、五点、图片、评论痛点拆成可验证假设。",
    icon: ClipboardCheck,
  },
  {
    title: "不再烧钱猜原因",
    desc: "用CTR、CVR、ACOS判断问题在流量、点击还是转化。",
    icon: Megaphone,
  },
  {
    title: "不再复盘断层",
    desc: "把命中和未命中的判断回流，下一轮越跑越准。",
    icon: RotateCcw,
  },
];

const plans = [
  { name: "免费试用", price: "0 元", desc: "先跑通一个ASIN的判断链路" },
  { name: "轻量版", price: "199 元/月", desc: "适合单店铺持续做小规模验证" },
  { name: "专业版", price: "699 元/月", desc: "适合把诊断、广告和复盘连起来", highlight: true },
  { name: "团队版", price: "1999 元/月", desc: "适合多账号、多店铺批量决策" },
];

export default function Landing() {
  const navigate = useNavigate();
  const workflowSteps = ["抓取真实数据", "统一评分判断", "诊断转化阻塞", "验证广告假设", "回流验证结果", "输出下一动作"];
  const heroSignals = ["选错品", "改错词", "烧错广告"];

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-gray-950">
      <nav className="sticky top-0 z-40 border-b border-black/5 bg-[#f5f5f7]/85 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <AlignXLogo showWordmark markClassName="h-8 w-8 rounded-lg" wordmarkClassName="text-lg" />
          <div className="hidden items-center gap-1 rounded-full border border-black/5 bg-white/70 p-1 text-sm font-medium text-gray-500 shadow-sm md:flex">
            <a href="#capabilities" className="rounded-full px-4 py-2 hover:bg-gray-100 hover:text-gray-950">决策能力</a>
            <a href="#pricing" className="rounded-full px-4 py-2 hover:bg-gray-100 hover:text-gray-950">定价</a>
            <button onClick={() => navigate("/terms")} className="rounded-full px-4 py-2 hover:bg-gray-100 hover:text-gray-950">用户协议</button>
            <button onClick={() => navigate("/login")} className="rounded-full px-4 py-2 hover:bg-gray-100 hover:text-gray-950">登录</button>
          </div>
          <Button onClick={() => navigate("/register")} className="h-9 rounded-full bg-brand-800 px-5 text-white hover:bg-brand-700">
            免费试用
          </Button>
        </div>
      </nav>

      <main>
        <section className="mx-auto grid min-h-[calc(100vh-56px)] max-w-7xl items-center gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[0.92fr_1.08fr] lg:px-8 lg:py-14">
          <div className="max-w-2xl">
            <Badge className="mb-5 rounded-full border-brand-200 bg-white px-3 py-1 text-brand-800 shadow-sm">
              AI运营决策系统
            </Badge>
            <h1 className="max-w-4xl text-4xl font-semibold leading-[1.04] tracking-tight text-gray-950 sm:text-5xl xl:text-6xl">
              把选品、Listing、广告验证变成可执行决策
            </h1>
            <p className="mt-6 max-w-xl text-base leading-8 text-gray-600 sm:text-lg">
              AlignX不是再给你一堆报告，而是帮卖家判断：这个ASIN要不要做、Listing先改哪里、广告该验证什么、下一轮动作怎么排。
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button onClick={() => navigate("/register")} size="lg" className="h-11 rounded-full bg-brand-800 px-6 text-white hover:bg-brand-700">
                进入决策工作台
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <Button onClick={() => navigate("/login")} size="lg" variant="outline" className="h-11 rounded-full border-gray-300 bg-white px-6">
                登录
              </Button>
            </div>
            <div className="mt-10 grid max-w-lg grid-cols-3 gap-3">
              {heroSignals.map((signal, index) => (
                <div key={signal} className="rounded-lg border border-black/5 bg-white/70 p-3 shadow-sm">
                  <div className="text-xs font-semibold text-brand-800">少{index + 1}步踩坑</div>
                  <div className="mt-2 text-sm font-semibold text-gray-900">{signal}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-white bg-white/75 p-3 shadow-[0_24px_80px_rgba(15,23,42,0.12)]">
            <div className="overflow-hidden rounded-lg border border-black/5 bg-[#fbfbfd]">
              <div className="flex items-center justify-between border-b border-black/5 px-5 py-4">
                <div>
                  <div className="text-sm font-semibold text-gray-950">运营判断链路</div>
                  <div className="mt-1 text-xs text-gray-500">从数据到动作</div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
                </div>
              </div>
              <div className="grid gap-4 p-5 lg:grid-cols-[1fr_0.82fr]">
                <div className="space-y-3">
                  {valueCards.map((item, index) => (
                    <div key={item.title} className="flex items-start gap-3 rounded-lg border border-black/5 bg-white p-4 shadow-sm">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-800">
                        <item.icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-semibold text-gray-400">{String(index + 1).padStart(2, "0")}</span>
                          <h3 className="text-sm font-semibold text-gray-950">{item.title}</h3>
                        </div>
                        <p className="mt-1 text-sm leading-6 text-gray-500">{item.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="rounded-lg border border-brand-900 bg-brand-900 p-4 text-white shadow-inner">
                  <div className="text-sm font-semibold text-gold-200">系统输出</div>
                  <div className="mt-4 space-y-2.5">
                    {workflowSteps.map((step, index) => (
                      <div key={step} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5">
                        <span className="text-xs font-semibold text-gold-300">{String(index + 1).padStart(2, "0")}</span>
                        <span className="text-sm font-medium text-white/95">{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="capabilities" className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
          <div className="grid gap-5 border-y border-black/5 py-8 lg:grid-cols-[0.32fr_1fr]">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">卖家最怕的不是没数据，是数据不能变成动作</h2>
              <p className="mt-2 text-sm leading-6 text-gray-500">AlignX把页面抓取、AI诊断、广告验证和复盘回流串成同一套判断标准。</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {valueCards.map((item) => (
                <div key={item.title} className="rounded-lg border border-black/5 bg-white p-5 shadow-sm">
                  <item.icon className="mb-5 h-5 w-5 text-brand-700" />
                  <h3 className="font-semibold text-gray-950">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-gray-500">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
          <div className="rounded-lg border border-black/5 bg-white p-4 shadow-sm sm:p-5">
            <h2 className="px-2 pb-4 text-2xl font-semibold tracking-tight">一条链路跑完整，才知道下一步该做什么</h2>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
              {workflowSteps.map((step, index) => (
                <div key={step} className="group flex min-h-24 flex-col justify-between rounded-lg border border-black/5 bg-[#f8f8fa] p-4">
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
              <h2 className="text-2xl font-semibold tracking-tight">先用一个ASIN验证判断质量</h2>
              <p className="mt-2 text-sm text-gray-500">从单品诊断开始，确认系统能帮你少走弯路，再扩大到多ASIN和广告闭环。</p>
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
