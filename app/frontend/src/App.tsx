import { Component, lazy, Suspense, type ReactNode } from 'react';
import { Toaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Landing from './pages/Landing';
import Login from './pages/Login';
import NotFound from './pages/NotFound';
// MODULE_IMPORTS_START
// MODULE_IMPORTS_END

const queryClient = new QueryClient();

const Dashboard = lazy(() => import('./pages/Dashboard'));
const AsinManager = lazy(() => import('./pages/AsinManager'));
const AdAnalytics = lazy(() => import('./pages/AdAnalytics'));
const Settings = lazy(() => import('./pages/Settings'));
const AuthCallback = lazy(() => import('./pages/AuthCallback'));
const Pricing = lazy(() => import('./pages/Pricing'));
const Terms = lazy(() => import('./pages/Terms'));
const Privacy = lazy(() => import('./pages/Privacy'));
const AuthError = lazy(() => import('./pages/AuthError'));
const CompetitorAnalysis = lazy(() => import('./pages/CompetitorAnalysis'));
const ListingDiagnosis = lazy(() => import('./pages/ListingDiagnosis'));
const PreLaunchTest = lazy(() => import('./pages/PreLaunchTest'));
const ABTestComparison = lazy(() => import('./pages/ABTestComparison'));
const OptimizationSuggestions = lazy(() => import('./pages/OptimizationSuggestions'));
const SuperAdmin = lazy(() => import('./pages/SuperAdmin'));

const PageLoader = () => (
  <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
    <div className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-6 text-center shadow-sm">
      <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-brand-100 border-t-brand-700" />
      <p className="text-sm font-semibold text-gray-900">正在加载 AlignX 模块</p>
      <p className="mt-1 text-xs text-gray-500">如果长时间停留，请按 Ctrl + F5 强制刷新。</p>
    </div>
  </div>
);

class AppErrorBoundary extends Component<{ children: ReactNode; routeKey: string }, { hasError: boolean; message: string }> {
  state = { hasError: false, message: '' };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: error.message || '页面加载失败' };
  }

  componentDidUpdate(prevProps: { routeKey: string }) {
    if (this.state.hasError && prevProps.routeKey !== this.props.routeKey) {
      this.setState({ hasError: false, message: '' });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 text-gray-900 flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
            <p className="text-sm font-semibold text-red-600 mb-2">页面模块加载失败</p>
            <h1 className="text-lg font-bold mb-2">请刷新或返回今日决策</h1>
            <p className="text-sm text-gray-500 mb-4">{this.state.message}</p>
            <button
              className="px-4 py-2 rounded-md bg-brand-600 text-white text-sm"
              onClick={() => { window.location.href = '/dashboard'; }}
            >
              返回今日决策
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const AppRoutes = () => {
  const location = useLocation();

  return (
    <AppErrorBoundary routeKey={`${location.pathname}${location.search}`}>
      <Suspense fallback={<PageLoader />}>
        <Routes location={location} key={`${location.pathname}${location.search}`}>
          <Route path="/" element={<Landing />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/asin-manager" element={<AsinManager />} />
          <Route path="/health-report" element={<ListingDiagnosis />} />

          <Route path="/ad-analytics" element={<AdAnalytics />} />
          <Route path="/ab-test-comparison" element={<ABTestComparison />} />
          <Route path="/competitor-analysis" element={<CompetitorAnalysis />} />
          <Route path="/listing-diagnosis" element={<ListingDiagnosis />} />
          <Route path="/alignxagent" element={<Dashboard />} />
          <Route path="/alignxagent/dashboard" element={<Dashboard />} />
          <Route path="/alignxagent/listing-diagnosis" element={<ListingDiagnosis />} />
          <Route path="/prelaunch-test" element={<PreLaunchTest />} />
          <Route path="/pre-launch-test" element={<PreLaunchTest />} />
          <Route path="/listing-launch-check" element={<PreLaunchTest />} />
          <Route path="/optimization-suggestions" element={<OptimizationSuggestions />} />
          <Route path="/admin" element={<SuperAdmin />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Login />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/auth/error" element={<AuthError />} />
          {/* MODULE_ROUTES_START */}
          {/* MODULE_ROUTES_END */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </AppErrorBoundary>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    {/* MODULE_PROVIDERS_START */}
    {/* MODULE_PROVIDERS_END */}
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
    {/* MODULE_PROVIDERS_CLOSE */}
  </QueryClientProvider>
);

export default App;
