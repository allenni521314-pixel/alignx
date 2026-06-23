import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";

// Lazy-loaded pages (Phase 3 implementation)
import MarketOpportunity from "./pages/MarketOpportunity";
import ProductResearch from "./pages/ProductResearch";
import CompetitorAnalysis from "./pages/CompetitorAnalysis";
import BusinessValidation from "./pages/BusinessValidation";
import YesterdayReport from "./pages/YesterdayReport";
import TodayDecisions from "./pages/TodayDecisions";
import PrelaunchCheck from "./pages/PrelaunchCheck";
import ConversionDiagnosis from "./pages/ConversionDiagnosis";
import TrafficStrategy from "./pages/TrafficStrategy";
import ExecutionRecords from "./pages/ExecutionRecords";
import ValidationResults from "./pages/ValidationResults";
import AccountCenter from "./pages/AccountCenter";

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <Routes>
          <Route path="/" element={<Navigate to="/market-opportunity" replace />} />
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
          <Route path="/validation-results" element={<ValidationResults />} />
          <Route path="/account" element={<AccountCenter />} />
        </Routes>
      </main>
    </div>
  );
}
