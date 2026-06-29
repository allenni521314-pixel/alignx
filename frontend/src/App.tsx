import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import HelpAssistant from "./components/help/HelpAssistant";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("alignx_token");
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

// Lazy-loaded pages (Phase 3 implementation)
import MarketOpportunity from "./pages/MarketOpportunity";
import PublicSite, { RootRedirect } from "./pages/PublicSite";
import Login from "./pages/Login";
import ProductResearch from "./pages/ProductResearch";
import CompetitorAnalysis from "./pages/CompetitorAnalysis";
import BusinessValidation from "./pages/BusinessValidation";
import YesterdayReport from "./pages/YesterdayReport";
import TodayDecisions from "./pages/TodayDecisions";
import PrelaunchCheck from "./pages/PrelaunchCheck";
import ConversionDiagnosis from "./pages/ConversionDiagnosis";
import TrafficStrategy from "./pages/TrafficStrategy";
import AccountCenter from "./pages/AccountCenter";
import AdminDashboard from "./pages/AdminDashboard";
import ExecutionRecords from "./pages/ExecutionRecords";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/en" element={<PublicSite />} />
      <Route path="/en/about" element={<PublicSite />} />
      <Route path="/en/privacy-policy" element={<PublicSite />} />
      <Route path="/en/terms" element={<PublicSite />} />
      <Route path="/en/data-use-policy" element={<PublicSite />} />
      <Route path="/en/security" element={<PublicSite />} />
      <Route path="/en/contact" element={<PublicSite />} />
      <Route path="/zh" element={<PublicSite />} />
      <Route path="/zh/about" element={<PublicSite />} />
      <Route path="/zh/privacy-policy" element={<PublicSite />} />
      <Route path="/zh/terms" element={<PublicSite />} />
      <Route path="/zh/data-use-policy" element={<PublicSite />} />
      <Route path="/zh/security" element={<PublicSite />} />
      <Route path="/zh/contact" element={<PublicSite />} />
      <Route path="/login" element={<Login />} />
      <Route path="*" element={
        <RequireAuth>
          <div className="min-h-screen">
            <Sidebar />
            <main className="min-h-screen overflow-y-auto p-6 pl-[244px]">
              <Routes>
          <Route path="/market-opportunity" element={<MarketOpportunity />} />
          <Route path="/product-research" element={<ProductResearch />} />
          <Route path="/competitor-analysis" element={<CompetitorAnalysis />} />
          <Route path="/business-validation" element={<BusinessValidation />} />
          <Route path="/yesterday-report" element={<YesterdayReport />} />
          <Route path="/today-decisions" element={<TodayDecisions />} />
          <Route path="/prelaunch-check" element={<PrelaunchCheck />} />
          <Route path="/conversion-diagnosis" element={<ConversionDiagnosis />} />
          <Route path="/traffic-strategy" element={<TrafficStrategy />} />
          <Route path="/execution-records" element={<ExecutionRecords />} />
          <Route path="/account" element={<AccountCenter />} />
          <Route path="/admin" element={<AdminDashboard />} />
        </Routes>
      </main>
      <HelpAssistant />
    </div>
        </RequireAuth>
      } />
    </Routes>
  );
}
