import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { AlignXLogo } from "@/components/AlignXLogo";
import { ArrowLeft, Loader2, Lock, Mail } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const FIXED_PASSWORD = "alignx2026";

export default function Login() {
  const navigate = useNavigate();
  const { phoneLogin } = useAuth();
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState(FIXED_PASSWORD);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!account.trim()) {
      setError("请输入手机号");
      return;
    }
    if (!password.trim()) {
      setError("请输入密码");
      return;
    }

    setLoading(true);
    try {
      await phoneLogin(account.trim(), password.trim());
      if (remember) localStorage.setItem("alignx_remember_login", "1");
      navigate("/dashboard");
    } catch (err: unknown) {
      const message =
        typeof err === "object" && err && "message" in err
          ? String((err as { message?: string }).message)
          : "登录失败，请检查账号或密码";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 text-gray-500 hover:text-gray-900 transition-colors mb-8 text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          返回首页
        </button>

        <Card className="bg-white border-gray-200 p-8 shadow-sm">
          <AlignXLogo
            showWordmark
            className="mb-8 justify-center"
            markClassName="h-11 w-11"
            wordmarkClassName="text-2xl"
          />

          <h1 className="text-2xl font-bold text-center">登录 AlignX</h1>
          <p className="text-gray-500 text-sm text-center mt-2 mb-8">
            进入你的亚马逊运营决策工作台
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label className="text-sm text-gray-600 flex items-center gap-2">
                <Mail className="w-4 h-4 text-brand-600" />
                手机号
              </label>
              <Input
                placeholder="请输入手机号"
                value={account}
                onChange={(e) => setAccount(e.target.value.replace(/\D/g, ""))}
                inputMode="numeric"
                className="h-12 bg-gray-50 border-gray-200"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-gray-600 flex items-center gap-2">
                <Lock className="w-4 h-4 text-brand-600" />
                密码
              </label>
              <Input
                type="password"
                placeholder="固定密码 alignx2026"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-12 bg-gray-50 border-gray-200"
              />
            </div>

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 text-gray-600">
                <Checkbox checked={remember} onCheckedChange={(v) => setRemember(v === true)} />
                记住我
              </label>
              <button type="button" className="text-brand-600 hover:text-brand-700">
                忘记密码
              </button>
            </div>

            {error && (
              <div className="text-red-600 text-sm bg-red-50 border border-red-100 rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-12 bg-brand-600 hover:bg-brand-500 text-white"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  登录中...
                </>
              ) : (
                "登录"
              )}
            </Button>
          </form>

          <p className="text-sm text-gray-500 text-center mt-6">
            没有账号？
            <button onClick={() => navigate("/register")} className="text-brand-600 hover:text-brand-700 ml-1">
              立即注册
            </button>
          </p>
        </Card>
      </div>
    </div>
  );
}
