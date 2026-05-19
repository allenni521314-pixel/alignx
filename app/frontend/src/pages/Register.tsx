import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { AlignXLogo } from "@/components/AlignXLogo";
import { ArrowLeft, Building2, Loader2, Lock, Phone } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const FIXED_PASSWORD = "alignx2026";

export default function Register() {
  const navigate = useNavigate();
  const { phoneLogin } = useAuth();
  const [name, setName] = useState("");
  const [account, setAccount] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!name.trim()) {
      setError("请输入姓名或公司名");
      return;
    }
    if (!account.trim()) {
      setError("请输入手机号");
      return;
    }
    const phone = account.trim();
    if (!/^\d{10,}$/.test(phone)) {
      setError("请输入有效手机号");
      return;
    }

    setLoading(true);
    try {
      await phoneLogin(phone, FIXED_PASSWORD);
      localStorage.setItem("alignx_trial_status", "trial");
      localStorage.setItem(
        "alignx_trial_user",
        JSON.stringify({
          name: name.trim(),
          account: phone,
          plan: "免费试用",
          expires_at: "2026-06-16",
        })
      );
      navigate("/dashboard");
    } catch (err: unknown) {
      const message =
        typeof err === "object" && err && "message" in err
          ? String((err as { message?: string }).message)
          : "注册失败，请检查手机号";
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

          <h1 className="text-2xl font-bold text-center">注册 AlignX</h1>
          <p className="text-gray-500 text-sm text-center mt-2 mb-8">
            注册后默认进入免费试用状态
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label className="text-sm text-gray-600 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-brand-600" />
                姓名 / 公司名
              </label>
              <Input value={name} onChange={(e) => setName(e.target.value)} className="h-12 bg-gray-50 border-gray-200" />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-gray-600 flex items-center gap-2">
                <Phone className="w-4 h-4 text-brand-600" />
                手机号
              </label>
              <Input
                value={account}
                onChange={(e) => setAccount(e.target.value.replace(/\D/g, ""))}
                placeholder="请输入手机号"
                inputMode="numeric"
                className="h-12 bg-gray-50 border-gray-200"
              />
            </div>

            <div className="rounded-lg border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-brand-700 flex items-center gap-2">
              <Lock className="w-4 h-4 shrink-0" />
              测试版固定密码：{FIXED_PASSWORD}
            </div>

            {error && (
              <div className="text-red-600 text-sm bg-red-50 border border-red-100 rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            <Button type="submit" disabled={loading} className="w-full h-12 bg-brand-600 hover:bg-brand-500 text-white">
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  注册中...
                </>
              ) : (
                "注册"
              )}
            </Button>
          </form>

          <p className="text-sm text-gray-500 text-center mt-6">
            已有账号？
            <button onClick={() => navigate("/login")} className="text-brand-600 hover:text-brand-700 ml-1">
              去登录
            </button>
          </p>
        </Card>
      </div>
    </div>
  );
}
