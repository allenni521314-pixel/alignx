import { NavLink } from "react-router-dom";
import {
  Globe,
  PackageSearch,
  BarChart3,
  ShieldCheck,
  FileText,
  Zap,
  ClipboardCheck,
  ArrowDownToLine,
  Route,
  ListChecks,
  CheckCircle2,
  User,
} from "lucide-react";

const NAV = [
  { to: "/market-opportunity", label: "市场机会", icon: Globe },
  { to: "/product-research", label: "产品调研", icon: PackageSearch },
  { to: "/competitor-analysis", label: "竞品分析", icon: BarChart3 },
  { to: "/business-validation", label: "经营验证", icon: ShieldCheck },
  { to: "/yesterday-report", label: "昨日战报", icon: FileText },
  { to: "/today-decisions", label: "今日决策", icon: Zap },
  { to: "/prelaunch-check", label: "上架准入", icon: ClipboardCheck },
  { to: "/conversion-diagnosis", label: "承接转化", icon: ArrowDownToLine },
  { to: "/traffic-strategy", label: "流量策略", icon: Route },
  { to: "/execution-records", label: "执行记录", icon: ListChecks },
  { to: "/validation-results", label: "效果验证", icon: CheckCircle2 },
  { to: "/account", label: "账号中心", icon: User },
];

export default function Sidebar() {
  return (
    <aside className="w-[220px] h-screen flex flex-col shrink-0 bg-white/80 backdrop-blur-xl border-r border-[#d2d2d7]/40">
      {/* Logo */}
      <div className="h-[52px] flex items-center gap-2.5 px-5 border-b border-[#d2d2d7]/20">
        <div className="w-7 h-7 rounded-lg bg-[#0071e3] flex items-center justify-center">
          <span className="text-white text-xs font-bold">A</span>
        </div>
        <span className="text-[17px] font-semibold tracking-tight">AlignX</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-xl text-[14px] font-medium
               transition-all duration-150 ${
                isActive
                  ? "bg-[#0071e3]/8 text-[#0071e3]"
                  : "text-[#1d1d1f]/70 hover:bg-[#f5f5f7] hover:text-[#1d1d1f]"
              }`
            }
          >
            <Icon size={18} strokeWidth={1.75} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-[#d2d2d7]/20">
        <p className="text-[12px] text-[#86868b] tracking-wide">
          先验证 · 再投入
        </p>
      </div>
    </aside>
  );
}
