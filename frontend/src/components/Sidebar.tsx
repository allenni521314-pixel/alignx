import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  PackageSearch,
  BarChart3,
  FileText,
  Zap,
  ClipboardCheck,
  ArrowDownToLine,
  Route,
  User,
  LogOut,
  Shield,
  ChevronDown,
  ChevronRight,
  Search,
  TrendingUp,
} from "lucide-react";

type NavItem = { to: string; label: string; icon: React.ComponentType<{ size?: number; strokeWidth?: number }> };
type NavGroup = { label: string; icon: React.ComponentType<{ size?: number }>; children: NavItem[] };

const NAV_GROUPS: (NavGroup | NavItem)[] = [
  {
    label: "机会选品",
    icon: Search,
    children: [
      { to: "/market-opportunity", label: "产品调研", icon: PackageSearch },
      { to: "/competitor-analysis", label: "竞品分析", icon: BarChart3 },
    ],
  },
  {
    label: "运营验证",
    icon: TrendingUp,
    children: [
      { to: "/yesterday-report", label: "昨日战报", icon: FileText },
      { to: "/today-decisions", label: "今日决策", icon: Zap },
      { to: "/conversion-diagnosis", label: "承接转化", icon: ArrowDownToLine },
      { to: "/traffic-strategy", label: "广告策略", icon: Route },
    ],
  },
  {
    label: "新品上架",
    icon: ClipboardCheck,
    children: [
      { to: "/prelaunch-check", label: "上架准入", icon: ClipboardCheck },
    ],
  },
];

const BOTTOM_NAV = [
  { to: "/account", label: "账号中心", icon: User },
];

export default function Sidebar() {
  const user = JSON.parse(localStorage.getItem("alignx_user") || "{}");
  const isAdmin = user.email === "allenni521314@gmail.com";
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({ "机会选品": true, "运营验证": true, "新品上架": true });

  return (
    <aside className="w-[220px] h-screen flex flex-col shrink-0 bg-white/80 backdrop-blur-xl border-r border-[#d2d2d7]/40">
      <div className="h-[52px] flex items-center gap-2.5 px-5 border-b border-[#d2d2d7]/20">
        <div className="w-7 h-7 rounded-lg bg-[#0071e3] flex items-center justify-center">
          <span className="text-white text-xs font-bold">A</span>
        </div>
        <span className="text-[17px] font-semibold tracking-tight">AlignX</span>
      </div>
      <div className="px-5 py-2 border-b border-[#d2d2d7]/20">
        <p className="text-[12px] text-[#86868b] tracking-wide">先验证 · 再投入</p>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
        {NAV_GROUPS.map((item, i) => {
          if ("children" in item) {
            const open = openGroups[item.label] ?? true;
            return (
              <div key={i}>
                <button
                  onClick={() => setOpenGroups({ ...openGroups, [item.label]: !open })}
                  className="flex items-center gap-2 w-full px-3 py-2 rounded-xl text-[13px] font-medium text-[#86868b] hover:text-[#1d1d1f] transition-colors"
                >
                  {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <item.icon size={16} />
                  <span>{item.label}</span>
                </button>
                {open && (
                  <div className="ml-2 space-y-0.5">
                    {item.children.map((child) => (
                      <NavLink
                        key={child.to}
                        to={child.to}
                        className={({ isActive }) =>
                          `flex items-center gap-3 px-3 py-2 rounded-xl text-[14px] font-medium transition-all duration-150 ${
                            isActive ? "bg-[#0071e3]/8 text-[#0071e3]" : "text-[#1d1d1f]/70 hover:bg-[#f5f5f7] hover:text-[#1d1d1f]"
                          }`
                        }
                      >
                        <child.icon size={18} strokeWidth={1.75} />
                        <span>{child.label}</span>
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            );
          }
          const { to, label, icon: Icon } = item as NavItem;
          return (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-xl text-[14px] font-medium transition-all duration-150 ${
                  isActive ? "bg-[#0071e3]/8 text-[#0071e3]" : "text-[#1d1d1f]/70 hover:bg-[#f5f5f7] hover:text-[#1d1d1f]"
                }`
              }
            >
              <Icon size={18} strokeWidth={1.75} />
              <span>{label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="px-3 py-2 border-t border-[#d2d2d7]/20 space-y-1">
        {BOTTOM_NAV.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2 rounded-xl text-[14px] font-medium transition-all duration-150 ${
              isActive ? "bg-[#0071e3]/8 text-[#0071e3]" : "text-[#1d1d1f]/70 hover:bg-[#f5f5f7] hover:text-[#1d1d1f]"
            }`}><Icon size={18} strokeWidth={1.75} /><span>{label}</span></NavLink>
        ))}
        {isAdmin && (
          <a href="/admin" className="flex items-center gap-2 text-[13px] text-[#86868b] hover:text-[#0071e3] transition-colors w-full no-underline">
            <Shield size={14} />
            管理后台
          </a>
        )}
        <button
          onClick={() => {
            localStorage.removeItem("alignx_token");
            localStorage.removeItem("alignx_user");
            window.location.href = "/login";
          }}
          className="flex items-center gap-2 text-[13px] text-[#86868b] hover:text-[#ff3b30] transition-colors w-full"
        >
          <LogOut size={14} />
          退出登录
        </button>
      </div>
    </aside>
  );
}
