import { useNavigate, useLocation } from "react-router-dom";
import {
  Package,
  BarChart3,
  Lightbulb,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  Target,
  Swords,
  FileSearch,
  ClipboardCheck,
  Stethoscope,
  Network,
  Megaphone,
  MessageSquareText,
  RotateCcw,
  Search,
  CalendarCheck,
  ShieldCheck,
  Sparkles,
  Layers3,
  Rocket,
  ClipboardList,
  Database,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { AlignXLogo } from "@/components/AlignXLogo";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  AlignX flow navigation                                             */
/* ------------------------------------------------------------------ */

interface NavItem {
  path: string;
  label: string;
  icon: React.ElementType;
  disabled?: boolean;
  locked?: boolean;
}

interface NavGroup {
  stage: string;
  title: string;
  icon: React.ElementType;
  color: string;
  activeColor: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    stage: "一",
    title: "选品决策",
    icon: Search,
    color: "text-brand-400",
    activeColor: "text-brand-600",
    items: [
      {
        path: "/asin-manager",
        label: "ASIN选品",
        icon: Layers3,
      },
    ],
  },
  {
    stage: "二",
    title: "Listing 运营",
    icon: Target,
    color: "text-teal-400",
    activeColor: "text-teal-600",
    items: [
      {
        path: "/listing-launch-check",
        label: "上新检测",
        icon: Rocket,
      },
      {
        path: "/competitor-analysis?tab=strategy",
        label: "竞品诊断",
        icon: Swords,
      },
      {
        path: "/listing-diagnosis",
        label: "本品诊断",
        icon: Stethoscope,
      },
    ],
  },
  {
    stage: "三",
    title: "广告投放",
    icon: Megaphone,
    color: "text-amber-400",
    activeColor: "text-amber-600",
    items: [
      { path: "/ab-test-comparison", label: "测试计划", icon: ClipboardList },
      { path: "/ad-analytics?view=records", label: "执行记录", icon: BarChart3 },
      { path: "/ad-analytics?view=validation", label: "效果验证", icon: ShieldCheck },
    ],
  },
  {
    stage: "四",
    title: "复盘优化",
    icon: RotateCcw,
    color: "text-emerald-400",
    activeColor: "text-emerald-600",
    items: [
      { path: "/optimization-suggestions?view=data-feedback", label: "数据回流", icon: Database },
      { path: "/optimization-suggestions?view=conclusion", label: "复盘结论", icon: MessageSquareText },
      {
        path: "/optimization-suggestions?view=next-round",
        label: "下一轮优化",
        icon: RotateCcw,
      },
    ],
  },
  {
    stage: "",
    title: "系统设置",
    icon: Settings,
    color: "text-gold-400",
    activeColor: "text-gold-600",
    items: [
      { path: "/settings", label: "超级管理员入口", icon: ShieldCheck },
    ],
  },
];

export function AppSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const handleLogout = async () => {
    localStorage.removeItem("alignx_token");
    localStorage.removeItem("alignx_user");
    navigate("/");
    window.location.reload();
  };

  const handleNav = (path: string) => {
    if (location.pathname + location.search === path) {
      window.location.reload();
      return;
    }
    if (path.includes("?")) {
      window.location.assign(path);
      return;
    }
    navigate(path);
    if (isMobile) setMobileOpen(false);
  };

  const showLabel = !collapsed || isMobile;

  /* Check if nav item is active */
  const isNavActive = (itemPath: string) => {
    if (itemPath.includes("?")) {
      return location.pathname + location.search === itemPath;
    }
    return location.pathname === itemPath;
  };

  /* Check if a group contains the active page */
  const isGroupActive = (group: NavGroup) => {
    return group.items.some((item) => {
      if (item.path.includes("?")) {
        return location.pathname + location.search === item.path;
      }
      return location.pathname === item.path;
    });
  };

  /* Render a single nav button */
  const renderNavButton = (item: NavItem, groupColor: string) => {
    const isActive = isNavActive(item.path);
    const isDisabled = item.disabled === true;
    return (
      <Tooltip key={item.path} delayDuration={0}>
        <TooltipTrigger asChild>
          <button
            onClick={() => !isDisabled && handleNav(item.path)}
            disabled={isDisabled}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-200 group relative",
              isDisabled
                ? "text-gray-400 cursor-not-allowed opacity-50"
                : isActive
                  ? "bg-gray-900 text-white shadow-sm"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
            )}
          >
            <item.icon
              className={cn(
                "w-[16px] h-[16px] flex-shrink-0 transition-colors",
                isDisabled
                  ? "text-gray-400"
                  : isActive
                    ? "text-white"
                    : `group-hover:${groupColor}`
              )}
            />
            {showLabel && (
              <span className="truncate flex items-center gap-1.5 min-w-0">
                <span className="truncate">{item.label}</span>
                {isDisabled && (
                  <span className="ml-1 text-[10px] text-gray-400">
                    (即将上线)
                  </span>
                )}
              </span>
            )}
          </button>
        </TooltipTrigger>
        {collapsed && !isMobile && (
          <TooltipContent
            side="right"
            className="bg-white text-gray-900 border-gray-200"
          >
            {item.label}
            {isDisabled ? " (即将上线)" : ""}
          </TooltipContent>
        )}
      </Tooltip>
    );
  };

  const sidebarContent = (
    <aside
      className={cn(
        "h-screen bg-white border-r border-gray-200 flex flex-col transition-all duration-300 flex-shrink-0",
        isMobile ? "w-64" : collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-gray-100">
        <button
          type="button"
          className="min-w-0 text-left"
          onClick={() => handleNav("/dashboard")}
          aria-label="返回 AlignX 今日决策"
        >
          <AlignXLogo
            showWordmark={showLabel}
            markClassName="h-9 w-9 rounded-xl"
            wordmarkClassName="text-base"
          />
        </button>
        {isMobile && (
          <button
            onClick={() => setMobileOpen(false)}
            className="ml-auto text-gray-500 hover:text-gray-900 p-1"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Flow-based Navigation */}
      <nav className="flex-1 py-2 px-2 overflow-y-auto">
        {/* 今日决策 — standalone top button */}
        <div className="mb-1">
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <button
                onClick={() => handleNav("/dashboard")}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] font-semibold transition-all duration-200 group",
                  location.pathname === "/dashboard"
                    ? "bg-gradient-to-r from-brand-600 to-gold-600 text-white shadow-md shadow-brand-200"
                    : "text-gray-700 hover:bg-brand-50 hover:text-brand-700 border border-transparent hover:border-brand-100"
                )}
              >
                <div
                  className={cn(
                    "w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors",
                    location.pathname === "/dashboard"
                      ? "bg-white/20"
                      : "bg-brand-50 group-hover:bg-brand-100"
                  )}
                >
                  <CalendarCheck
                    className={cn(
                      "w-4 h-4",
                      location.pathname === "/dashboard"
                        ? "text-white"
                        : "text-brand-600"
                    )}
                  />
                </div>
                {showLabel && <span>今日决策</span>}
              </button>
            </TooltipTrigger>
            {collapsed && !isMobile && (
              <TooltipContent
                side="right"
                className="bg-white text-gray-900 border-gray-200"
              >
                今日决策
              </TooltipContent>
            )}
          </Tooltip>
        </div>

        {navGroups.map((group) => {
          const groupActive = isGroupActive(group);
          return (
            <div key={group.title} className="mb-0.5">
              {showLabel && (
                <div
                  className={cn(
                    "px-3 pt-4 pb-1.5 text-[11px] font-bold tracking-wider uppercase select-none flex items-center gap-1.5 transition-colors",
                    groupActive ? group.activeColor : "text-gray-400"
                  )}
                >
                  <span className="text-[13px]">{group.stage}</span>
                  <group.icon className="w-3 h-3" />
                  {group.title}
                  {groupActive && (
                    <span className="ml-auto w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                  )}
                </div>
              )}
              {!showLabel && (
                <div className="my-1 mx-3 border-t border-gray-100" />
              )}
              <div className="space-y-0.5">
                {group.items.map((item) =>
                  renderNavButton(item, group.activeColor)
                )}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Bottom: Logout + Collapse */}
      <div className="p-2 border-t border-gray-100 space-y-0.5">
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium text-gray-500 hover:text-red-500 hover:bg-red-50 transition-colors"
            >
              <LogOut className="w-[16px] h-[16px] flex-shrink-0" />
              {showLabel && <span>退出登录</span>}
            </button>
          </TooltipTrigger>
          {collapsed && !isMobile && (
            <TooltipContent
              side="right"
              className="bg-white text-gray-900 border-gray-200"
            >
              退出登录
            </TooltipContent>
          )}
        </Tooltip>
        {!isMobile && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed(!collapsed)}
            className="w-full flex items-center justify-center text-gray-400 hover:text-gray-900 hover:bg-gray-50"
          >
            {collapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </Button>
        )}
      </div>
    </aside>
  );

  if (isMobile) {
    return (
      <>
        <button
          onClick={() => setMobileOpen(true)}
          className="fixed top-3 left-3 z-50 w-10 h-10 rounded-xl bg-white/90 backdrop-blur border border-gray-200 flex items-center justify-center text-gray-600 hover:text-gray-900 md:hidden shadow-lg"
        >
          <Menu className="w-5 h-5" />
        </button>

        {mobileOpen && (
          <div className="fixed inset-0 z-50 flex md:hidden">
            <div
              className="absolute inset-0 bg-black/20 backdrop-blur-sm"
              onClick={() => setMobileOpen(false)}
            />
            <div className="relative z-10 animate-in slide-in-from-left duration-300">
              {sidebarContent}
            </div>
          </div>
        )}
      </>
    );
  }

  return (
    <>
      {sidebarContent}
    </>
  );
}
