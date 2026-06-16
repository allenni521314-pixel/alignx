import {
  AsinBusinessProfile,
  AiDecisionTrace,
  AsinModuleView,
  AsinModuleViewType,
  DailySnapshot,
  DemoImportResponse,
  ExecutionLog,
  MetricDictionaryItem,
  ValidationTask,
  clearDemoAsinProfileData,
  getAsinProfile,
  getAsinModuleView,
  importDemoFromListingDiagnosis,
  listAiDecisionTraces,
  listAsinProfiles,
  listDailySnapshots,
  listExecutionLogs,
  listMetricDictionary,
  listValidationTasks,
} from "@/lib/asin-business-profile-api";

type LoadState = "idle" | "loading" | "ready" | "error";

interface AsinBusinessProfileState {
  status: LoadState;
  activeProfile: AsinBusinessProfile | null;
  profiles: AsinBusinessProfile[];
  dailySnapshots: DailySnapshot[];
  validationTasks: ValidationTask[];
  executionLogs: ExecutionLog[];
  aiDecisionTraces: AiDecisionTrace[];
  moduleViews: Partial<Record<AsinModuleViewType, AsinModuleView>>;
  metrics: MetricDictionaryItem[];
  demoImport: DemoImportResponse | null;
  error: string | null;
}

const state: AsinBusinessProfileState = {
  status: "idle",
  activeProfile: null,
  profiles: [],
  dailySnapshots: [],
  validationTasks: [],
  executionLogs: [],
  aiDecisionTraces: [],
  moduleViews: {},
  metrics: [],
  demoImport: null,
  error: null,
};

const listeners = new Set<(nextState: AsinBusinessProfileState) => void>();

function emit() {
  const nextState = getAsinBusinessProfileState();
  listeners.forEach((listener) => listener(nextState));
}

function setState(patch: Partial<AsinBusinessProfileState>) {
  Object.assign(state, patch);
  emit();
}

export function getAsinBusinessProfileState(): AsinBusinessProfileState {
  return {
    ...state,
    profiles: [...state.profiles],
    dailySnapshots: [...state.dailySnapshots],
    validationTasks: [...state.validationTasks],
    executionLogs: [...state.executionLogs],
    aiDecisionTraces: [...state.aiDecisionTraces],
    moduleViews: { ...state.moduleViews },
    metrics: [...state.metrics],
  };
}

export function subscribeAsinBusinessProfileStore(
  listener: (nextState: AsinBusinessProfileState) => void
): () => void {
  listeners.add(listener);
  listener(getAsinBusinessProfileState());
  return () => listeners.delete(listener);
}

export async function loadAsinBusinessProfiles(params: {
  store_id?: string;
  marketplace?: string;
  is_demo?: boolean;
  skip?: number;
  limit?: number;
} = {}) {
  setState({ status: "loading", error: null });
  try {
    const data = await listAsinProfiles(params);
    setState({ status: "ready", profiles: data.items, error: null });
    return data;
  } catch (error) {
    setState({ status: "error", error: error instanceof Error ? error.message : "暂无" });
    throw error;
  }
}

export async function loadAsinBusinessProfile(params: {
  marketplace: string;
  asin: string;
  store_id?: string;
}) {
  setState({ status: "loading", error: null });
  try {
    const data = await getAsinProfile(params);
    setState({ status: "ready", activeProfile: data, error: null });
    return data;
  } catch (error) {
    setState({ status: "error", error: error instanceof Error ? error.message : "暂无" });
    throw error;
  }
}

export async function loadAsinValidationTasks(params: {
  asin?: string;
  store_id?: string;
  marketplace?: string;
  skip?: number;
  limit?: number;
} = {}) {
  const data = await listValidationTasks(params);
  setState({ validationTasks: data.items });
  return data;
}

export async function loadAsinDailySnapshots(params: {
  asin?: string;
  store_id?: string;
  marketplace?: string;
  skip?: number;
  limit?: number;
} = {}) {
  const data = await listDailySnapshots(params);
  setState({ dailySnapshots: data.items });
  return data;
}

export async function loadAsinExecutionLogs(params: {
  asin?: string;
  validation_id?: string;
  store_id?: string;
  marketplace?: string;
  skip?: number;
  limit?: number;
} = {}) {
  const data = await listExecutionLogs(params);
  setState({ executionLogs: data.items });
  return data;
}

export async function loadAsinAiDecisionTraces(params: {
  asin?: string;
  decision_type?: string;
  related_validation_id?: string;
  store_id?: string;
  marketplace?: string;
  skip?: number;
  limit?: number;
} = {}) {
  const data = await listAiDecisionTraces(params);
  setState({ aiDecisionTraces: data.items });
  return data;
}

export async function loadMetricDictionary() {
  const data = await listMetricDictionary();
  setState({ metrics: data });
  return data;
}

export async function loadAsinModuleView(params: {
  view_type: AsinModuleViewType;
  asin?: string;
  store_id?: string;
  marketplace?: string;
}) {
  setState({ status: "loading", error: null });
  try {
    const data = await getAsinModuleView(params);
    setState({
      status: "ready",
      moduleViews: {
        ...state.moduleViews,
        [params.view_type]: data,
      },
      error: null,
    });
    return data;
  } catch (error) {
    setState({ status: "error", error: error instanceof Error ? error.message : "暂无" });
    throw error;
  }
}

export async function importDemoAsinProfiles(params: {
  store_id?: string;
  marketplace?: string;
  limit?: number;
} = {}) {
  setState({ status: "loading", error: null });
  try {
    const data = await importDemoFromListingDiagnosis(params);
    setState({ status: "ready", demoImport: data, error: null });
    return data;
  } catch (error) {
    setState({ status: "error", error: error instanceof Error ? error.message : "暂无" });
    throw error;
  }
}

export async function clearDemoAsinProfiles() {
  const data = await clearDemoAsinProfileData();
  setState({ demoImport: null });
  return data;
}
