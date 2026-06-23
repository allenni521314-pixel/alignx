import { NavLink } from "react-router-dom";
import {
  TrendingUp,
  Search,
  BarChart3,
  ShieldCheck,
  FileText,
  Lightbulb,
  ClipboardCheck,
  ArrowDownToLine,
  Route,
  Play,
  CheckCircle2,
  User,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/market-opportunity", label: "市场机会", icon: TrendingUp },
  { to: "/product-research", label: "产品调研", icon: Search },
  { to: "/competitor-analysis", label: "竞品分析", icon: BarChart3 },
  { to: "/business-validation", label: "经营验证", icon: ShieldCheck },
  { to: "/yesterday-report", label: "昨日战报", icon: FileText },
  { to: "/today-decisions", label: "今日决策", icon: Lightbulb },
  { to: "/prelaunch-check", label: "上架准入", icon: ClipboardCheck },
  { to: "/conversion-diagnosis", label: "承接转化", icon: ArrowDownToLine },
  { to: "/traffic-strategy", label: "流量策略", icon: Route },
  { to: "/execution-records", label: "执行记录", icon: Play },
  { to: "/validation-results", label: "效果验证", icon: CheckCircle2 },
  { to: "/account", label: "账号中心", icon: User },
];

export default function Sidebar() {
  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0">
      {/* Brand */}
      <div className="h-14 flex items-center px-4 border-b border-gray-100">
        <span className="text-lg font-bold text-brand-700">AlignX</span>
        <span className="ml-2 text-xs text-gray-400">V1</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                isActive
                  ? "bg-brand-50 text-brand-700 font-medium border-r-2 border-brand-600"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-100 text-xs text-gray-400">
        先验证，再投入
      </div>
    </aside>
  );
}
