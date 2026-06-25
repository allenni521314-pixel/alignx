import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Database, BookOpen, GitBranch, Activity, Languages, ArrowRight, Copy, Shield } from "lucide-react";
import { API_BASE } from "@/lib/api";

const API = API_BASE + "/admin";

export default function AdminDashboard() {
  const user = JSON.parse(localStorage.getItem("alignx_user") || "{}");
  if (user.email !== "allenni521314@gmail.com") {
    window.location.href = "/login";
    return null;
  }
  const { data: props, isLoading: lp } = useQuery({ queryKey: ["admin-props"], queryFn: () => fetch(`${API}/propositions`).then(r => r.json()), enabled: true });
  const { data: profiles, isLoading: la } = useQuery({ queryKey: ["admin-profiles"], queryFn: () => fetch(`${API}/asin-profiles`).then(r => r.json()), enabled: true });
  const { data: audit } = useQuery({ queryKey: ["admin-audit"], queryFn: () => fetch(`${API}/audit`).then(r => r.json()), enabled: true });

  if (lp || la) return <div className="max-w-[900px] mx-auto py-8"><div className="apple-card p-16 text-center"><div className="w-8 h-8 border-2 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mx-auto" /></div></div>;

  const loop = audit?.loop_health ?? {};

  return (
    <div className="max-w-[900px] mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-[28px] font-bold tracking-[-0.025em] mb-1">管理后台</h1>
        <p className="text-[15px] text-[#86868b]">命题库 · ASIN 档案 · 闭环审计</p>
      </div>

      {/* Loop Health */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        <AuditCard label="命题库" ok={loop.has_propositions} />
        <AuditCard label="验证任务" ok={loop.has_tasks} />
        <AuditCard label="执行记录" ok={loop.has_executions} />
        <AuditCard label="验证结果" ok={loop.has_results} />
        <AuditCard label="闭环完整" ok={loop.loop_complete} />
      </div>

      {/* ASIN Profiles */}
      <div className="apple-card p-5 mb-6">
        <h3 className="flex items-center gap-2 text-[15px] font-semibold mb-3"><Database size={16} className="text-[#0071e3]" />ASIN 经营档案 ({profiles?.length ?? 0})</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead><tr className="border-b border-[#d2d2d7]/20 text-left text-[#86868b]">
              <th className="py-2 pr-4">ASIN</th><th className="py-2 pr-4">标题</th><th className="py-2 pr-4">阶段</th><th className="py-2 pr-4">验证次数</th><th className="py-2 pr-4">有效</th><th className="py-2 pr-4">无效</th><th className="py-2 pr-4">当前问题</th>
            </tr></thead>
            <tbody>
              {(profiles ?? []).map((p: any) => (
                <tr key={p.asin} className="border-b border-[#d2d2d7]/10">
                  <td className="py-2 pr-4 font-mono text-[12px]">{p.asin}</td>
                  <td className="py-2 pr-4 max-w-[200px] truncate">{p.product_title || "—"}</td>
                  <td className="py-2 pr-4">{p.lifecycle_stage || "—"}</td>
                  <td className="py-2 pr-4">{p.total_validation_count}</td>
                  <td className="py-2 pr-4 text-[#34c759]">{p.effective_count}</td>
                  <td className="py-2 pr-4 text-[#ff3b30]">{p.ineffective_count}</td>
                  <td className="py-2 pr-4 max-w-[200px] truncate">{p.current_main_problem || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Buyer Language Translator */}
      <BuyerLangTool />

      {/* Platform Rules */}
      <RulesLibrary />

      {/* Propositions */}
      <div className="apple-card p-5">
        <h3 className="flex items-center gap-2 text-[15px] font-semibold mb-3"><BookOpen size={16} className="text-[#0071e3]" />命题库 ({props?.length ?? 0})</h3>
        <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
          <table className="w-full text-[13px]">
            <thead><tr className="border-b border-[#d2d2d7]/20 text-left text-[#86868b] sticky top-0 bg-white">
              <th className="py-2 pr-3">编码</th><th className="py-2 pr-3">分类</th><th className="py-2 pr-3">标题</th><th className="py-2 pr-3">假设模板</th>
            </tr></thead>
            <tbody>
              {(props ?? []).map((p: any) => (
                <tr key={p.id} className="border-b border-[#d2d2d7]/10">
                  <td className="py-2 pr-3 font-mono text-[12px]">{p.code}</td>
                  <td className="py-2 pr-3">{p.category}</td>
                  <td className="py-2 pr-3">{p.title}</td>
                  <td className="py-2 pr-3 max-w-[300px] truncate text-[#86868b]">{p.hypothesis_template || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function AuditCard({ label, ok }: { label: string; ok?: boolean }) {
  const color = ok ? "text-[#34c759] bg-[#34c759]/[0.06]" : "text-[#ff3b30] bg-[#ff3b30]/[0.06]";
  return (
    <div className={`apple-card p-3 text-center ${color}`}>
      <p className="text-[22px] font-bold">{ok ? "✓" : "✗"}</p>
      <p className="text-[11px] mt-0.5">{label}</p>
    </div>
  );
}

function RulesLibrary() {
  const { data: rules } = useQuery({ queryKey: ["admin-rules"], queryFn: () => fetch(`${API}/rules`).then(r => r.json()), enabled: true });
  const [editing, setEditing] = useState<string | null>(null);
  const [editItems, setEditItems] = useState("");

  const handleEdit = (ruleId: string, items: string[]) => {
    setEditing(ruleId);
    setEditItems(items.join("\n"));
  };

  const handleSave = async (ruleId: string) => {
    const items = editItems.split("\n").filter(i => i.trim());
    await fetch(`${API}/rules/${ruleId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(items),
    });
    setEditing(null);
  };

  if (!rules) return null;

  return (
    <div className="apple-card p-5 mb-6">
      <h3 className="flex items-center gap-2 text-[15px] font-semibold mb-3"><Shield size={16} className="text-[#0071e3]" />平台规则库</h3>
      <div className="grid grid-cols-2 gap-3">
        {Object.entries(rules).map(([id, rule]: [string, any]) => (
          <div key={id} className="border border-[#d2d2d7]/20 rounded-xl p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${rule.risk === "high" ? "bg-[#ff3b30]/10 text-[#ff3b30]" : rule.risk === "medium" ? "bg-[#ff9500]/10 text-[#ff9500]" : "bg-[#f5f5f7] text-[#86868b]"}`}>{rule.category}</span>
              <span className="text-[13px] font-medium">{rule.name}</span>
            </div>
            <p className="text-[11px] text-[#86868b] mb-2">{rule.description}</p>
            {editing === id ? (
              <div>
                <textarea value={editItems} onChange={e => setEditItems(e.target.value)} rows={4} className="apple-input text-[12px] mb-2" />
                <div className="flex gap-2">
                  <button onClick={() => handleSave(id)} className="apple-btn-primary text-[12px] px-3 py-1">保存</button>
                  <button onClick={() => setEditing(null)} className="apple-btn-secondary text-[12px] px-3 py-1">取消</button>
                </div>
              </div>
            ) : (
              <div>
                <div className="text-[11px] text-[#86868b] max-h-[80px] overflow-y-auto">
                  {rule.items.slice(0, 5).map((item: string, i: number) => <p key={i} className="truncate">· {item}</p>)}
                  {rule.items.length > 5 && <p className="text-[#0071e3]">+{rule.items.length - 5} 条</p>}
                </div>
                <button onClick={() => handleEdit(id, rule.items)} className="text-[12px] text-[#0071e3] mt-1">编辑</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function BuyerLangTool() {
  const [claims, setClaims] = useState("");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const handleTranslate = async () => {
    if (!claims.trim()) return;
    setLoading(true);
    try {
      const r = await fetch(`${API}/buyer-lang-translate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_info: { title: title || "未提供" },
          seller_claims: claims.split("\n").filter(c => c.trim()),
        }),
      });
      setResult(await r.json());
    } catch {} finally { setLoading(false); }
  };

  return (
    <div className="apple-card p-5 mb-6">
      <h3 className="flex items-center gap-2 text-[15px] font-semibold mb-3"><Languages size={16} className="text-[#0071e3]" />买家语言转译引擎</h3>
      <p className="text-[13px] text-[#86868b] mb-3">卖家技术语言 → 亚马逊买家购买语言</p>

      <div className="space-y-3 mb-4">
        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="产品标题（可选）" className="apple-input" />
        <textarea value={claims} onChange={e => setClaims(e.target.value)} placeholder="卖家原始卖点，每行一个" rows={4} className="apple-input" />
        <button onClick={handleTranslate} disabled={loading || !claims.trim()} className="apple-btn-primary flex items-center gap-2 px-4 py-2 text-[14px]">
          <ArrowRight size={14} /> {loading ? "转译中..." : "转译成买家语言"}
        </button>
      </div>

      {result?.seller_claims?.map((c: any, i: number) => (
        <div key={i} className="border border-[#d2d2d7]/20 rounded-xl p-4 mb-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[12px] px-1.5 py-0.5 rounded bg-[#86868b]/10 text-[#86868b]">{c.claim_type}</span>
            <span className={`text-[12px] px-1.5 py-0.5 rounded ${c.final_score >= 4 ? "bg-[#34c759]/10 text-[#34c759]" : c.final_score >= 3 ? "bg-[#ff9500]/10 text-[#ff9500]" : "bg-[#ff3b30]/10 text-[#ff3b30]"}`}>评分 {c.final_score}</span>
            <span className="text-[12px] text-[#86868b]">{c.usable_status}</span>
          </div>
          <p className="text-[13px] text-[#ff3b30] mb-1">❌ 卖家语言：{c.original_claim}</p>
          <p className="text-[12px] text-[#86868b] mb-2">问题：{c.problem}</p>

          {["short", "bullet", "aplus"].map(style => {
            const key = `buyer_language_${style}` as string;
            const val = c[key];
            if (!val) return null;
            return (
              <div key={style} className="flex items-start justify-between gap-2 p-2 rounded-lg bg-[#f5f5f7] mb-1">
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] text-[#86868b] uppercase mb-0.5">{style === "short" ? "标题/主图" : style === "bullet" ? "五点描述" : "A+"}</p>
                  <p className="text-[13px] text-[#0071e3]">{val}</p>
                </div>
                <button onClick={() => { navigator.clipboard.writeText(val); setCopied(`${i}-${style}`); setTimeout(() => setCopied(null), 2000); }} className="shrink-0 text-[12px] text-[#0071e3] hover:text-[#0077ed]">
                  {copied === `${i}-${style}` ? "已复制" : "复制"}
                </button>
              </div>
            );
          })}

          <div className="flex items-center gap-2 mt-2">
            <span className="text-[11px] text-[#86868b]">位置：{c.listing_position}</span>
            <span className="text-[11px] text-[#86868b]">验证：{c.metric_to_validate}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
