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
  ListChecks,
  User,
  LogOut,
  Shield,
  Database,
  ReceiptText,
  CreditCard,
  ChevronDown,
  ChevronRight,
  Search,
  TrendingUp,
} from "lucide-react";

type NavItem = { to: string; label: string; icon: React.ComponentType<{ size?: number; strokeWidth?: number }> };
type NavGroup = { label: string; icon: React.ComponentType<{ size?: number }>; children: NavItem[] };

const NAV_GROUPS: (NavGroup | NavItem)[] = [
  {
    label: "市场机会",
    icon: Search,
    children: [
      { to: "/market-opportunity", label: "产品机会", icon: PackageSearch },
      { to: "/competitor-analysis", label: "竞品分析", icon: BarChart3 },
    ],
  },
  {
    label: "新品上架",
    icon: ClipboardCheck,
    children: [
      { to: "/prelaunch-check", label: "上架准入", icon: ClipboardCheck },
    ],
  },
  {
    label: "运营验证",
    icon: TrendingUp,
    children: [
      { to: "/yesterday-report", label: "昨日战报", icon: FileText },
      { to: "/today-decisions", label: "今日决策", icon: Zap },
      { to: "/conversion-diagnosis", label: "承接转化", icon: ArrowDownToLine },
      { to: "/traffic-strategy", label: "广告测试", icon: Route },
      { to: "/execution-records", label: "执行记录", icon: ListChecks },
      { to: "/business-validation", label: "效果验证", icon: Shield },
    ],
  },
];

const ACCOUNT_GROUP: NavGroup = {
  label: "账号中心",
  icon: User,
  children: [
    { to: "/account#data-center", label: "数据中心", icon: Database },
    { to: "/account#recharge-records", label: "充值记录", icon: CreditCard },
    { to: "/account#spending-records", label: "消费记录", icon: ReceiptText },
  ],
};

export default function Sidebar() {
  const user = JSON.parse(localStorage.getItem("alignx_user") || "{}");
  const isAdmin = user.email === "allenni521314@gmail.com";
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({
    "市场机会": true,
    "新品上架": true,
    "运营验证": true,
    "账号中心": false,
  });

  return (
    <aside className="fixed left-0 top-0 w-[220px] h-screen flex flex-col bg-white/80 backdrop-blur-xl border-r border-[#d2d2d7]/40 z-20">
      <div className="h-[58px] flex items-center px-5 border-b border-[#d2d2d7]/20">
        <img
          src="/alignx-logo.png"
          alt="AlignX"
          className="h-[34px] w-auto max-w-[150px] object-contain"
        />
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
                            isActive ? "bg-[#0F2A24]/8 text-[#0F2A24]" : "text-[#1d1d1f]/70 hover:bg-[#fbfaf7] hover:text-[#1d1d1f]"
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
                  isActive ? "bg-[#0F2A24]/8 text-[#0F2A24]" : "text-[#1d1d1f]/70 hover:bg-[#fbfaf7] hover:text-[#1d1d1f]"
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
        <div>
          <button
            onClick={() => setOpenGroups({ ...openGroups, [ACCOUNT_GROUP.label]: !openGroups[ACCOUNT_GROUP.label] })}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-xl text-[14px] font-medium text-[#1d1d1f]/70 hover:bg-[#fbfaf7] hover:text-[#1d1d1f] transition-colors"
          >
            {openGroups[ACCOUNT_GROUP.label] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <ACCOUNT_GROUP.icon size={18} />
            <span>{ACCOUNT_GROUP.label}</span>
          </button>
          {openGroups[ACCOUNT_GROUP.label] && (
            <div className="ml-2 space-y-0.5">
              {ACCOUNT_GROUP.children.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-xl text-[13px] font-medium transition-all duration-150 ${
                    isActive ? "bg-[#0F2A24]/8 text-[#0F2A24]" : "text-[#1d1d1f]/70 hover:bg-[#fbfaf7] hover:text-[#1d1d1f]"
                  }`}><Icon size={16} strokeWidth={1.75} /><span>{label}</span></NavLink>
              ))}
            </div>
          )}
        </div>
        {isAdmin && (
          <a href="/admin" className="flex items-center gap-2 text-[13px] text-[#86868b] hover:text-[#0F2A24] transition-colors w-full no-underline">
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
