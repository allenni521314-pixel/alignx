import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { Home } from "lucide-react";

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-900">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-brand-600 mb-4">404</h1>
        <p className="text-xl text-gray-500 mb-8">页面未找到</p>
        <Button
          onClick={() => navigate("/")}
          className="bg-brand-600 hover:bg-brand-500 text-white"
        >
          <Home className="w-4 h-4 mr-2" />
          返回首页
        </Button>
      </div>
    </div>
  );
}