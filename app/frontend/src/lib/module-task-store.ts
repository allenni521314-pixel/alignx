export type ModuleTaskStatus = "pending" | "running" | "completed" | "failed";

export type ModuleTaskKey =
  | "asin-manager"
  | "listing-launch-check"
  | "competitor-analysis"
  | "listing-diagnosis"
  | "ab-test-comparison"
  | "ad-analytics"
  | "optimization-suggestions"
  | "settings";

export interface ModuleTaskRecord {
  id: string;
  moduleKey: ModuleTaskKey;
  label: string;
  status: ModuleTaskStatus;
  detail?: string;
  path?: string;
  startedAt: string;
  updatedAt: string;
}

const STORE_KEY = "alignx_module_tasks_v1";
const TASK_EVENT = "alignx-module-tasks-updated";
const ACTIVE_TTL_MS = 8 * 60 * 60 * 1000;
const FINISHED_TTL_MS = 10 * 60 * 1000;

const nowIso = () => new Date().toISOString();

const isBrowser = () => typeof window !== "undefined";

const parseTime = (value?: string) => {
  const time = value ? new Date(value).getTime() : 0;
  return Number.isFinite(time) ? time : 0;
};

const isFreshTask = (task: ModuleTaskRecord) => {
  const age = Date.now() - parseTime(task.updatedAt || task.startedAt);
  if (task.status === "pending" || task.status === "running") {
    return age <= ACTIVE_TTL_MS;
  }
  return age <= FINISHED_TTL_MS;
};

const readTasks = (): ModuleTaskRecord[] => {
  if (!isBrowser()) return [];
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((task) => task?.id && task?.moduleKey && task?.status).filter(isFreshTask);
  } catch {
    return [];
  }
};

const writeTasks = (tasks: ModuleTaskRecord[]) => {
  if (!isBrowser()) return;
  window.localStorage.setItem(STORE_KEY, JSON.stringify(tasks.filter(isFreshTask)));
  window.dispatchEvent(new Event(TASK_EVENT));
};

export const listModuleTasks = () => readTasks();

export const listActiveModuleTasks = () =>
  readTasks().filter((task) => task.status === "pending" || task.status === "running");

export const upsertModuleTask = (
  task: Omit<ModuleTaskRecord, "startedAt" | "updatedAt"> & {
    startedAt?: string;
    updatedAt?: string;
  }
) => {
  const tasks = readTasks();
  const existing = tasks.find((item) => item.id === task.id);
  const next: ModuleTaskRecord = {
    ...existing,
    ...task,
    startedAt: task.startedAt || existing?.startedAt || nowIso(),
    updatedAt: task.updatedAt || nowIso(),
  };
  writeTasks([next, ...tasks.filter((item) => item.id !== task.id)]);
  return next;
};

export const finishModuleTask = (id: string, status: "completed" | "failed", detail?: string) => {
  const tasks = readTasks();
  const task = tasks.find((item) => item.id === id);
  if (!task) return;
  writeTasks([
    {
      ...task,
      status,
      detail: detail || task.detail,
      updatedAt: nowIso(),
    },
    ...tasks.filter((item) => item.id !== id),
  ]);
};

export const removeModuleTask = (id: string) => {
  writeTasks(readTasks().filter((task) => task.id !== id));
};

export const subscribeModuleTasks = (callback: () => void) => {
  if (!isBrowser()) return () => {};
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORE_KEY || event.key === null) callback();
  };
  window.addEventListener(TASK_EVENT, callback);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(TASK_EVENT, callback);
    window.removeEventListener("storage", onStorage);
  };
};
