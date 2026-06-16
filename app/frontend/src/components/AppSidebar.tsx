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
  Search,
  CalendarCheck,
  ShieldCheck,
  Sparkles,
  Layers3,
  Rocket,
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
import {
  listActiveModuleTasks,
  subscribeModuleTasks,
  type ModuleTaskKey,
} from "@/lib/module-task-store";

/* ------------------------------------------------------------------ */
/*  AlignX flow navigation                                             */
/* ------------------------------------------------------------------ */

interface NavItem {
  path: string;
  label: string;
  icon: React.ElementType;
  moduleKey: ModuleTaskKey;
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
    title: "市场机会",
    icon: Search,
    color: "text-brand-400",
    activeColor: "text-brand-600",
    items: [
      {
        path: "/asin-manager",
        label: "关键词调研",
        icon: Layers3,
        moduleKey: "asin-manager",
      },
      {
        path: "/competitor-analysis?tab=score",
        label: "竞品打法",
        icon: Swords,
        moduleKey: "competitor-analysis",
      },
    ],
  },
  {
    stage: "二",
    title: "商品诊断",
    icon: Target,
    color: "text-teal-400",
    activeColor: "text-teal-600",
    items: [
      {
        path: "/listing-launch-check",
        label: "上架准入",
        icon: Rocket,
        moduleKey: "listing-launch-check",
      },
      {
        path: "/listing-diagnosis",
        label: "转化承接",
        icon: Stethoscope,
        moduleKey: "listing-diagnosis",
      },
    ],
  },
  {
    stage: "三",
    title: "广告验证",
    icon: Megaphone,
    color: "text-amber-400",
    activeColor: "text-amber-600",
    items: [
      { path: "/advertising-strategy", label: "流量策略", icon: Target, moduleKey: "advertising-strategy" },
      { path: "/ad-analytics?view=records", label: "执行记录", icon: BarChart3, moduleKey: "ad-analytics" },
      { path: "/ad-analytics?view=validation", label: "效果验证", icon: ShieldCheck, moduleKey: "ad-analytics" },
    ],
  },
  {
    stage: "",
    title: "账号中心",
    icon: Settings,
    color: "text-gold-400",
    activeColor: "text-gold-600",
    items: [
      { path: "/settings?tab=account", label: "账号信息", icon: Settings, moduleKey: "settings" },
    ],
  },
  {
    stage: "",
    title: "系统设置",
    icon: Settings,
    color: "text-gold-400",
    activeColor: "text-gold-600",
    items: [
      { path: "/settings", label: "系统设置", icon: Settings, moduleKey: "settings" },
    ],
  },
];

const pathOnly = (path: string) => path.split("?")[0];

const navPathCounts = navGroups
  .flatMap((group) => group.items.map((item) => pathOnly(item.path)))
  .reduce<Record<string, number>>((counts, pathname) => {
    counts[pathname] = (counts[pathname] || 0) + 1;
    return counts;
  }, {});

const isSharedPath = (pathname: string) => (navPathCounts[pathname] || 0) > 1;

const readTaskCounts = () => {
  const counts: Record<string, number> = {};
  listActiveModuleTasks().forEach((task) => {
    counts[task.moduleKey] = (counts[task.moduleKey] || 0) + 1;
  });
  return counts;
};

export function AppSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [taskCounts, setTaskCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  useEffect(() => {
    const refresh = () => setTaskCounts(readTaskCounts());
    refresh();
    const unsubscribe = subscribeModuleTasks(refresh);
    const timer = window.setInterval(refresh, 3000);
    return () => {
      unsubscribe();
      window.clearInterval(timer);
    };
  }, []);

  const handleLogout = async () => {
    localStorage.removeItem("alignx_token");
    localStorage.removeItem("alignx_user");
    localStorage.removeItem("token");
    navigate("/");
    window.location.reload();
  };

  const showLabel = !collapsed || isMobile;

  /* Check if nav item is active */
  const isNavActive = (itemPath: string) => {
    const [pathname, query = ""] = itemPath.split("?");
    if (location.pathname !== pathname) return false;
    if (!query || !isSharedPath(pathname)) return true;

    const expected = new URLSearchParams(query);
    const current = new URLSearchParams(location.search);
    for (const [key, value] of expected.entries()) {
      if (current.get(key) !== value) return false;
    }
    return true;
  };

  const handleNav = (path: string) => {
    if (isNavActive(path)) {
      if (isMobile) setMobileOpen(false);
      return;
    }
    navigate(path);
    if (isMobile) setMobileOpen(false);
  };

  /* Check if a group contains the active page */
  const isGroupActive = (group: NavGroup) => {
    return group.items.some((item) => isNavActive(item.path));
  };

  /* Render a single nav button */
  const renderNavButton = (item: NavItem) => {
    const isActive = isNavActive(item.path);
    const isDisabled = item.disabled === true;
    const activeTaskCount = taskCounts[item.moduleKey] || 0;
    const showTaskBadge = activeTaskCount > 0 && !isActive;
    return (
      <Tooltip key={item.path} delayDuration={0}>
        <TooltipTrigger asChild>
          <button
            onClick={() => !isDisabled && handleNav(item.path)}
            disabled={isDisabled}
            className={cn(
              "relative flex w-full items-center gap-2 rounded-lg border px-2 py-2 text-[13px] font-semibold transition-all duration-200 group",
              isDisabled
                ? "text-brand-200/35 cursor-not-allowed opacity-50"
                : isActive
                  ? "border-white/80 bg-white text-brand-900 shadow-sm"
                  : "border-transparent text-brand-100/75 hover:bg-white/10 hover:text-white"
            )}
          >
            {isActive && (
              <span className="absolute left-1 top-2 bottom-2 w-0.5 rounded-full bg-gold-400" />
            )}
            <item.icon
              className={cn(
                "h-[15px] w-[15px] flex-shrink-0 transition-colors",
                isDisabled
                  ? "text-brand-200/35"
                  : isActive
                    ? "text-brand-800"
                    : "text-brand-100/60 group-hover:text-white"
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
                {showTaskBadge && (
                  <span
                    className={cn(
                      "ml-auto inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold",
                      isActive ? "bg-brand-100 text-brand-700" : "bg-emerald-50 text-emerald-700"
                    )}
                    title="该模块有分析正在进行"
                  >
                    {activeTaskCount}
                  </span>
                )}
              </span>
            )}
            {!showLabel && showTaskBadge && (
              <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-emerald-500 ring-2 ring-white" />
            )}
          </button>
        </TooltipTrigger>
        {collapsed && !isMobile && (
          <TooltipContent
            side="right"
            className="bg-white text-gray-900 border-gray-200"
          >
            {item.label}
            {showTaskBadge ? ` · ${activeTaskCount} 个分析进行中` : ""}
            {isDisabled ? " (即将上线)" : ""}
          </TooltipContent>
        )}
      </Tooltip>
    );
  };

  const sidebarContent = (
    <aside
      className={cn(
        "h-screen flex-shrink-0 border-r border-brand-700/70 bg-brand-900/95 text-brand-50 backdrop-blur-xl flex flex-col transition-all duration-300",
        isMobile ? "w-64" : collapsed ? "w-16" : "w-[180px]"
      )}
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-3 border-b border-brand-700/60">
        <button
          type="button"
          className="min-w-0 text-left"
          onClick={() => handleNav("/dashboard")}
          aria-label="返回 AlignX 今日决策"
        >
          <AlignXLogo
            className="gap-2"
            showWordmark={showLabel}
            variant="light"
            markClassName="h-5 w-auto max-w-[40px]"
            wordmarkClassName="h-10 text-white"
          />
        </button>
        {isMobile && (
          <button
            onClick={() => setMobileOpen(false)}
            className="ml-auto text-brand-100/70 hover:text-white p-1"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Flow-based Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-2">
        {/* 今日决策 — standalone top button */}
        <div className="mb-2">
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <button
                onClick={() => handleNav("/dashboard")}
                className={cn(
                  "relative flex w-full items-center gap-2 rounded-lg border px-2 py-2 text-[13px] font-semibold transition-all duration-200 group",
                  location.pathname === "/dashboard"
                    ? "border-white/80 bg-white text-brand-900 shadow-sm"
                    : "border-transparent text-brand-100/80 hover:bg-white/10 hover:text-white"
                )}
              >
                {location.pathname === "/dashboard" && (
                  <span className="absolute left-1 top-2 bottom-2 w-0.5 rounded-full bg-gold-400" />
                )}
                <CalendarCheck
                  className={cn(
                    "h-[15px] w-[15px] flex-shrink-0",
                    location.pathname === "/dashboard"
                      ? "text-brand-800"
                      : "text-brand-100/70 group-hover:text-white"
                  )}
                />
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
          <div className="mt-1">
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <button
                onClick={() => handleNav("/yesterday-report")}
                className={cn(
                  "relative flex w-full items-center gap-2 rounded-lg border px-2 py-2 text-[13px] font-semibold transition-all duration-200 group",
                  location.pathname === "/yesterday-report"
                    ? "border-white/80 bg-white text-brand-900 shadow-sm"
                    : "border-transparent text-brand-100/75 hover:bg-white/10 hover:text-white"
                )}
              >
                {location.pathname === "/yesterday-report" && (
                  <span className="absolute left-1 top-2 bottom-2 w-0.5 rounded-full bg-gold-400" />
                )}
                <ClipboardCheck
                  className={cn(
                    "h-[15px] w-[15px] flex-shrink-0",
                    location.pathname === "/yesterday-report"
                      ? "text-brand-800"
                      : "text-brand-100/60 group-hover:text-white"
                  )}
                />
                {showLabel && <span className="truncate">昨日战报</span>}
              </button>
            </TooltipTrigger>
            {collapsed && !isMobile && (
              <TooltipContent
                side="right"
                className="bg-white text-gray-900 border-gray-200"
              >
                昨日战报
              </TooltipContent>
            )}
          </Tooltip>
          </div>
        </div>

        {navGroups.map((group) => {
          const groupActive = isGroupActive(group);
          return (
            <div key={group.title} className="mb-2">
              {showLabel && (
                <div
                  className={cn(
                    "flex select-none items-center gap-1 px-2 pb-1 pt-2.5 text-[11px] font-semibold transition-colors",
                    groupActive ? "text-gold-300" : "text-brand-100/45"
                  )}
                >
                  <span className="inline-flex h-3.5 min-w-3.5 items-center justify-center rounded-full border border-current/20 px-0.5 text-[9px] leading-none">
                    {group.stage || "设"}
                  </span>
                  <group.icon className="h-2.5 w-2.5" />
                  {group.title}
                  {groupActive && (
                    <span className="ml-auto h-1.5 w-1.5 rounded-full bg-current" />
                  )}
                </div>
              )}
              {!showLabel && (
                <div className="my-1 mx-3 border-t border-white/10" />
              )}
              <div className="space-y-0.5">
                {group.items.map((item) =>
                  renderNavButton(item)
                )}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Bottom: Logout + Collapse */}
      <div className="p-1.5 border-t border-brand-700/60 space-y-0.5">
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2 px-2 py-2 rounded-lg text-[13px] font-medium text-brand-100/65 hover:text-white hover:bg-white/10 transition-colors"
            >
              <LogOut className="h-[15px] w-[15px] flex-shrink-0" />
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
            className="w-full flex items-center justify-center text-brand-100/55 hover:text-white hover:bg-white/10"
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
