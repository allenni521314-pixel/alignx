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
    title: "ASIN 决策",
    icon: Search,
    color: "text-brand-400",
    activeColor: "text-brand-600",
    items: [
      {
        path: "/asin-manager",
        label: "选品决策",
        icon: Layers3,
        moduleKey: "asin-manager",
      },
    ],
  },
  {
    stage: "二",
    title: "Listing 诊断",
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
        path: "/competitor-analysis?tab=strategy",
        label: "竞品打法",
        icon: Swords,
        moduleKey: "competitor-analysis",
      },
      {
        path: "/listing-diagnosis",
        label: "承接诊断",
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
      { path: "/ab-test-comparison", label: "测试计划", icon: ClipboardList, moduleKey: "ab-test-comparison" },
      { path: "/ad-analytics?view=records", label: "执行记录", icon: BarChart3, moduleKey: "ad-analytics" },
      { path: "/ad-analytics?view=validation", label: "效果验证", icon: ShieldCheck, moduleKey: "ad-analytics" },
    ],
  },
  {
    stage: "四",
    title: "闭环优化",
    icon: RotateCcw,
    color: "text-emerald-400",
    activeColor: "text-emerald-600",
    items: [
      { path: "/optimization-suggestions?view=data-feedback", label: "数据回流", icon: Database, moduleKey: "optimization-suggestions" },
      { path: "/optimization-suggestions?view=conclusion", label: "复盘结论", icon: MessageSquareText, moduleKey: "optimization-suggestions" },
      {
        path: "/optimization-suggestions?view=next-round",
        label: "下一轮动作",
        icon: RotateCcw,
        moduleKey: "optimization-suggestions",
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
              "relative flex w-full items-center gap-2.5 rounded-xl border px-2.5 py-2 text-[13px] font-medium transition-all duration-200 group",
              isDisabled
                ? "text-gray-400 cursor-not-allowed opacity-50"
                : isActive
                  ? "border-gray-200 bg-gray-100/90 text-gray-950 shadow-sm"
                  : "border-transparent text-gray-600 hover:bg-gray-100/75 hover:text-gray-950"
            )}
          >
            {isActive && (
              <span className="absolute left-1 top-2 bottom-2 w-0.5 rounded-full bg-gray-950" />
            )}
            <item.icon
              className={cn(
                "w-[16px] h-[16px] flex-shrink-0 transition-colors",
                isDisabled
                  ? "text-gray-400"
                  : isActive
                    ? "text-gray-950"
                    : "text-gray-400 group-hover:text-gray-700"
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
        "h-screen flex-shrink-0 border-r border-gray-200/60 bg-white/85 backdrop-blur-xl flex flex-col transition-all duration-300",
        isMobile ? "w-64" : collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-gray-100">
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
      <nav className="flex-1 overflow-y-auto px-2.5 py-3">
        {/* 今日决策 — standalone top button */}
        <div className="mb-2">
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <button
                onClick={() => handleNav("/dashboard")}
                className={cn(
                  "w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl text-[13px] font-semibold transition-all duration-200 group border",
                  location.pathname === "/dashboard"
                    ? "border-gray-900 bg-gray-950 text-white shadow-sm"
                    : "border-transparent text-gray-700 hover:bg-gray-100/80 hover:text-gray-950"
                )}
              >
                <div
                  className={cn(
                    "w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors",
                    location.pathname === "/dashboard"
                      ? "bg-white/15"
                      : "bg-gray-100 group-hover:bg-white"
                  )}
                >
                  <CalendarCheck
                    className={cn(
                      "w-4 h-4",
                      location.pathname === "/dashboard"
                        ? "text-white"
                        : "text-gray-700"
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
            <div key={group.title} className="mb-2.5">
              {showLabel && (
                <div
                  className={cn(
                    "flex select-none items-center gap-1.5 px-2.5 pb-1 pt-2.5 text-[11px] font-semibold transition-colors",
                    groupActive ? group.activeColor : "text-gray-400"
                  )}
                >
                  <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full border border-current/20 px-1 text-[10px] leading-none">
                    {group.stage || "设"}
                  </span>
                  <group.icon className="w-3 h-3" />
                  {group.title}
                  {groupActive && (
                    <span className="ml-auto h-1.5 w-1.5 rounded-full bg-current" />
                  )}
                </div>
              )}
              {!showLabel && (
                <div className="my-1 mx-3 border-t border-gray-100" />
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
