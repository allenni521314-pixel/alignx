import { Component, type ReactNode } from 'react';
import { Toaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import AsinManager from './pages/AsinManager';
import AdAnalytics from './pages/AdAnalytics';
import Settings from './pages/Settings';
import AuthCallback from './pages/AuthCallback';
import Login from './pages/Login';
import Register from './pages/Register';
import Pricing from './pages/Pricing';
import AuthError from './pages/AuthError';
import CompetitorAnalysis from './pages/CompetitorAnalysis';
import ListingDiagnosis from './pages/ListingDiagnosis';
import PreLaunchTest from './pages/PreLaunchTest';
import ABTestComparison from './pages/ABTestComparison';

import OptimizationSuggestions from './pages/OptimizationSuggestions';
import SuperAdmin from './pages/SuperAdmin';
import NotFound from './pages/NotFound';
// MODULE_IMPORTS_START
// MODULE_IMPORTS_END

const queryClient = new QueryClient();

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
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/auth/error" element={<AuthError />} />
        {/* MODULE_ROUTES_START */}
        {/* MODULE_ROUTES_END */}
        <Route path="*" element={<NotFound />} />
      </Routes>
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
