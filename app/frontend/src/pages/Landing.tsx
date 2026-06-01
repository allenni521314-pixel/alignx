import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
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
    title: "少选错品",
    desc: "判断 ASIN 是否值得继续投入。",
    icon: Layers3,
  },
  {
    title: "少无效改版",
    desc: "定位 Listing 的流量承接问题。",
    icon: ClipboardCheck,
  },
  {
    title: "少盲目烧广告",
    desc: "看清广告数据验证的问题。",
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
              让每一步运营，都有正确判断。
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-gray-600">
              减少选品误判，定位承接问题，看清广告验证结果。
            </p>
          </div>

          <div id="capabilities" className="mx-auto mt-16 grid max-w-5xl gap-px overflow-hidden rounded-lg border border-black/5 bg-black/5 md:grid-cols-3">
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
