import { ArrowUpRight } from "lucide-react";

const sections = [
  {
    id: "why",
    title: "运营不该靠猜。",
    body: [
      "广告烧了，订单没涨。",
      "Listing 改了，转化掉了。",
      "新品上了，库存压住了。",
      "团队每天都在操作，但很多动作没有依据。",
    ],
    close: "真正亏掉利润的，往往不是一笔广告费。而是一连串没有验证过的决定。",
  },
  {
    id: "how",
    title: "在投入之前，先看清楚。",
    body: [
      "这个产品值不值得继续做。",
      "Listing 有没有说清楚买家真正关心的理由。",
      "广告预算该放大、收缩，还是暂停。",
      "问题出在流量、价格、图片，还是转化承接。",
      "每一次动作有没有结果可以复盘。",
    ],
  },
  {
    id: "profile",
    title: "每一个 ASIN，都应该有自己的经营档案。",
    body: [
      "从上架、改图、投广告、调价格到复盘，所有关键动作都应该留下判断记录。",
    ],
    close: "不是记录数据。是记住每一次判断。",
  },
];

const steps = [
  ["先判断", "这次投入到底想解决什么问题。"],
  ["再执行", "让图片、文案、关键词、广告和预算围绕同一个方向展开。"],
  ["看结果", "用真实数据判断继续、调整，还是停止。"],
];

const sellers = [
  "多 SKU 卖家",
  "新品测试卖家",
  "广告投入较大的卖家",
  "运营团队负责人",
  "想减少错误投入的品牌卖家",
];

export default function LandingHome() {
  return (
    <div className="min-h-screen bg-[#fbfaf7] text-[#0F2A24]">
      <header className="sticky top-0 z-20 border-b border-[#0F2A24]/10 bg-[#fbfaf7]/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1120px] items-center justify-between px-5">
          <a href="/" className="text-[22px] font-semibold tracking-[-0.03em] text-[#0F2A24]">
            AlignX
          </a>
          <nav className="hidden items-center gap-8 text-[14px] text-[#0F2A24]/70 md:flex">
            <a href="#why" className="transition-colors hover:text-[#0F2A24]">为什么 AlignX</a>
            <a href="#how" className="transition-colors hover:text-[#0F2A24]">如何验证</a>
            <a href="#for-who" className="transition-colors hover:text-[#0F2A24]">适合谁</a>
          </nav>
          <a
            href="/login"
            className="rounded-full bg-[#0F2A24] px-4 py-2 text-[14px] font-medium text-white transition-colors hover:bg-[#173a32]"
          >
            登录 / 开始验证
          </a>
        </div>
      </header>

      <main>
        <section className="mx-auto grid min-h-[680px] max-w-[1120px] items-center gap-12 px-5 py-20 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <p className="mb-6 text-[15px] font-medium text-[#B18742]">先验证，再投入。</p>
            <h1 className="max-w-[760px] text-[48px] font-semibold leading-[1.04] tracking-[-0.055em] text-[#0F2A24] sm:text-[64px]">
              掌握每一次运营投入
            </h1>
            <p className="mt-7 max-w-[680px] text-[22px] leading-[1.45] tracking-[-0.03em] text-[#0F2A24]/78">
              别再让广告、Listing、新品和备货，变成事后才知道的错误。
            </p>
            <p className="mt-5 max-w-[620px] text-[17px] leading-[1.75] text-[#0F2A24]/64">
              AlignX 帮助亚马逊卖家在投入之前，看清问题，判断方向，再决定是否放大。
            </p>
          </div>

          <div className="rounded-[28px] border border-[#0F2A24]/12 bg-white p-6 shadow-[0_24px_80px_rgba(15,42,36,0.10)]">
            <div className="mb-6 flex items-center justify-between border-b border-[#0F2A24]/10 pb-5">
              <div>
                <p className="text-[13px] text-[#0F2A24]/50">ASIN 状态</p>
                <p className="mt-1 text-[20px] font-semibold tracking-[-0.03em]">投入前待验证</p>
              </div>
              <div className="rounded-full bg-[#0F2A24]/8 px-3 py-1 text-[12px] font-medium text-[#0F2A24]">
                待判断
              </div>
            </div>
            <div className="space-y-5">
              <CardLine label="当前问题" value="Listing 承接不清" />
              <CardLine label="建议动作" value="先验证，再放大" />
              <CardLine label="投入判断" value="看清楚后再决定" />
            </div>
          </div>
        </section>

        {sections.map((section) => (
          <section key={section.id} id={section.id} className="border-t border-[#0F2A24]/8">
            <div className="mx-auto max-w-[900px] px-5 py-24">
              <h2 className="text-[36px] font-semibold tracking-[-0.045em] text-[#0F2A24]">{section.title}</h2>
              <div className="mt-8 space-y-3 text-[19px] leading-[1.75] text-[#0F2A24]/72">
                {section.body.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
              {section.close && (
                <p className="mt-10 max-w-[720px] text-[24px] font-medium leading-[1.45] tracking-[-0.035em] text-[#0F2A24]">
                  {section.close}
                </p>
              )}
            </div>
          </section>
        ))}

        <section className="border-t border-[#0F2A24]/8 bg-white" id="method">
          <div className="mx-auto max-w-[980px] px-5 py-24">
            <h2 className="text-[36px] font-semibold tracking-[-0.045em]">先验证，再投入。</h2>
            <div className="mt-10 grid gap-4 md:grid-cols-3">
              {steps.map(([title, text]) => (
                <div key={title} className="rounded-2xl border border-[#0F2A24]/10 bg-[#fbfaf7] p-6">
                  <p className="text-[18px] font-semibold tracking-[-0.03em]">{title}</p>
                  <p className="mt-4 text-[15px] leading-[1.7] text-[#0F2A24]/65">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="for-who" className="border-t border-[#0F2A24]/8">
          <div className="mx-auto max-w-[980px] px-5 py-24">
            <h2 className="text-[36px] font-semibold tracking-[-0.045em]">适合这些卖家</h2>
            <div className="mt-9 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {sellers.map((seller) => (
                <div key={seller} className="rounded-2xl border border-[#0F2A24]/10 bg-white p-5 text-[15px] font-medium text-[#0F2A24]/78">
                  {seller}
                </div>
              ))}
            </div>
            <div className="mt-20 rounded-[28px] bg-[#0F2A24] p-8 text-white sm:p-12">
              <p className="text-[30px] font-semibold tracking-[-0.045em]">下一笔投入之前，先验证。</p>
              <p className="mt-5 text-[18px] text-white/70">掌握每一次运营投入。</p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#0F2A24]/10">
        <div className="mx-auto flex max-w-[1120px] flex-col gap-2 px-5 py-10 text-[14px] text-[#0F2A24]/60 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-semibold text-[#0F2A24]">AlignX</p>
          <p>掌握每一次运营投入</p>
          <p>先验证，再投入</p>
        </div>
      </footer>
    </div>
  );
}

function CardLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-5 rounded-2xl bg-[#0F2A24]/[0.035] p-4">
      <div>
        <p className="text-[12px] text-[#0F2A24]/45">{label}</p>
        <p className="mt-1 text-[17px] font-medium tracking-[-0.03em] text-[#0F2A24]">{value}</p>
      </div>
      <ArrowUpRight size={18} className="text-[#B18742]" />
    </div>
  );
}
