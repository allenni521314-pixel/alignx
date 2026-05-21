import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { AlignXLogo } from "@/components/AlignXLogo";
import { ArrowLeft, Building2, Loader2, Lock, Phone, ShieldCheck } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const FIXED_PASSWORD = "alignx2026";

export default function Login() {
  const navigate = useNavigate();
  const { phoneLogin } = useAuth();
  const [storeName, setStoreName] = useState("");
  const [phone, setPhone] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    const cleanStoreName = storeName.trim();
    const cleanPhone = phone.trim();

    if (!cleanStoreName) {
      setError("请输入测试公司或亚马逊店铺名称");
      return;
    }
    if (cleanStoreName.length < 2) {
      setError("公司或店铺名称至少需要2个字符");
      return;
    }
    if (!cleanPhone) {
      setError("请输入手机号");
      return;
    }
    if (!/^1[3-9]\d{9}$/.test(cleanPhone)) {
      setError("请输入正确的11位手机号");
      return;
    }

    setLoading(true);
    try {
      await phoneLogin(cleanPhone, FIXED_PASSWORD, cleanStoreName);
      if (remember) localStorage.setItem("alignx_remember_login", "1");
      localStorage.setItem(
        "alignx_trial_user",
        JSON.stringify({
          name: cleanStoreName,
          account: cleanPhone,
          plan: "内测版",
          login_type: "beta_store_phone",
        })
      );
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

          <h1 className="text-2xl font-bold text-center">登录 AlignX 内测工作台</h1>
          <p className="text-gray-500 text-sm text-center mt-2 mb-8">
            请填写真实公司或亚马逊店铺名称，便于内测记录与问题回访。
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label className="text-sm text-gray-600 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-brand-600" />
                公司 / 亚马逊店铺名称
              </label>
              <Input
                placeholder="例如：深圳XX科技 / XX Amazon Store"
                value={storeName}
                onChange={(e) => setStoreName(e.target.value)}
                className="h-12 bg-gray-50 border-gray-200"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-gray-600 flex items-center gap-2">
                <Phone className="w-4 h-4 text-brand-600" />
                手机号
              </label>
              <Input
                placeholder="请输入11位手机号"
                value={phone}
                onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 11))}
                inputMode="numeric"
                className="h-12 bg-gray-50 border-gray-200"
              />
            </div>

            <div className="rounded-lg border border-brand-100 bg-brand-50 px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-brand-700">
                <Lock className="w-4 h-4 shrink-0" />
                测试密码已自动填充
              </div>
              <p className="mt-1 text-xs text-gray-500">
                内测版本统一使用固定测试密码，登录时系统会自动提交。
              </p>
            </div>

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 text-gray-600">
                <Checkbox checked={remember} onCheckedChange={(v) => setRemember(v === true)} />
                记住我
              </label>
              <span className="inline-flex items-center gap-1 text-brand-600">
                <ShieldCheck className="w-4 h-4" />
                内测登录
              </span>
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
                "进入今日决策工作台"
              )}
            </Button>
          </form>

          <p className="text-xs text-gray-400 text-center mt-6">
            新用户填写以上信息即可进入，无需单独注册。
          </p>
        </Card>
      </div>
    </div>
  );
}
