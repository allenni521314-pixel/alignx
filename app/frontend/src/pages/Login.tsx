import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { AlignXLogo } from "@/components/AlignXLogo";
import { ArrowLeft, Building2, KeyRound, Loader2, Mail, ShieldCheck } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, loading: authLoading, sendEmailCode, emailLogin } = useAuth();
  const [storeName, setStoreName] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [remember, setRemember] = useState(true);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [loading, setLoading] = useState(false);

  const redirectTarget = (() => {
    const stateFrom = (location.state as { from?: string } | null)?.from;
    const queryFrom = new URLSearchParams(location.search).get("from");
    const target = stateFrom || queryFrom || "/dashboard";
    return target.startsWith("/login") ? "/dashboard" : target;
  })();

  useEffect(() => {
    if (!authLoading && user) {
      navigate(redirectTarget, { replace: true });
    }
  }, [authLoading, navigate, redirectTarget, user]);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("alignx_trial_user") || "{}");
      if (localStorage.getItem("alignx_remember_login") === "1") {
        if (saved.name) setStoreName(String(saved.name));
        if (saved.account) setEmail(String(saved.account));
        if (localStorage.getItem("alignx_terms_accepted") === "1") setAcceptedTerms(true);
      }
    } catch {
      // Ignore malformed local storage from older beta builds.
    }
  }, []);

  const validateBase = () => {
    const cleanStoreName = storeName.trim();
    const cleanEmail = email.trim().toLowerCase();

    if (!cleanStoreName) {
      setError("请输入测试公司或亚马逊店铺名称");
      return null;
    }
    if (cleanStoreName.length < 2) {
      setError("公司或店铺名称至少需要2个字符");
      return null;
    }
    if (!cleanEmail) {
      setError("请输入邮箱");
      return null;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      setError("请输入正确的邮箱地址");
      return null;
    }
    if (!acceptedTerms) {
      setError("请先阅读并同意用户协议和隐私政策");
      return null;
    }

    return { cleanStoreName, cleanEmail };
  };

  const handleSendCode = async () => {
    setError("");
    setNotice("");
    const base = validateBase();
    if (!base) return;

    setSendingCode(true);
    try {
      const res = await sendEmailCode(base.cleanEmail, base.cleanStoreName);
      setCodeSent(true);
      if (res.debugCode) {
        setError(`验证码：${res.debugCode}`);
      } else {
        setNotice("验证码已发送，请查看邮箱");
      }
    } catch (err: unknown) {
      const message =
        typeof err === "object" && err && "message" in err
          ? String((err as { message?: string }).message)
          : "验证码发送失败，请稍后重试";
      setError(message);
    } finally {
      setSendingCode(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");

    const base = validateBase();
    if (!base) return;

    const cleanCode = code.trim();
    if (!/^\d{6}$/.test(cleanCode)) {
      setError("请输入6位邮箱验证码");
      return;
    }

    setLoading(true);
    try {
      await emailLogin(base.cleanEmail, cleanCode, base.cleanStoreName);
      if (remember) {
        localStorage.setItem("alignx_remember_login", "1");
        localStorage.setItem(
          "alignx_trial_user",
          JSON.stringify({
            name: base.cleanStoreName,
            account: base.cleanEmail,
            plan: "内测版",
            login_type: "beta_store_email",
          })
        );
        localStorage.setItem("alignx_terms_accepted", "1");
      } else {
        localStorage.removeItem("alignx_remember_login");
        localStorage.removeItem("alignx_trial_user");
        localStorage.removeItem("alignx_terms_accepted");
      }
      navigate(redirectTarget);
    } catch (err: unknown) {
      const message =
        typeof err === "object" && err && "message" in err
          ? String((err as { message?: string }).message)
          : "登录失败，请检查邮箱或验证码";
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
                <Mail className="w-4 h-4 text-brand-600" />
                邮箱
              </label>
              <Input
                placeholder="请输入邮箱地址"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                inputMode="email"
                className="h-12 bg-gray-50 border-gray-200"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-gray-600 flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-brand-600" />
                邮箱验证码
              </label>
              <div className="flex gap-2">
                <Input
                  placeholder="请输入6位验证码"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  className="h-12 bg-gray-50 border-gray-200"
                />
                <Button
                  type="button"
                  variant="outline"
                  disabled={sendingCode || !acceptedTerms}
                  onClick={handleSendCode}
                  className="h-12 min-w-[112px]"
                >
                  {sendingCode ? <Loader2 className="w-4 h-4 animate-spin" /> : codeSent ? "重新发送" : "发送验证码"}
                </Button>
              </div>
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

            <label className="flex items-start gap-2 text-xs text-gray-500 leading-5">
              <Checkbox checked={acceptedTerms} onCheckedChange={(v) => setAcceptedTerms(v === true)} className="mt-0.5" />
              <span>
                我已阅读并同意
                <button type="button" onClick={() => navigate("/terms")} className="mx-1 text-brand-700 hover:text-brand-900 underline underline-offset-2">
                  用户协议
                </button>
                和
                <button type="button" onClick={() => navigate("/privacy")} className="mx-1 text-brand-700 hover:text-brand-900 underline underline-offset-2">
                  隐私政策
                </button>
              </span>
            </label>

            {error && (
              <div className="text-red-600 text-sm bg-red-50 border border-red-100 rounded-lg px-4 py-3">
                {error}
              </div>
            )}
            {notice && (
              <div className="text-brand-700 text-sm bg-brand-50 border border-brand-100 rounded-lg px-4 py-3">
                {notice}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading || !acceptedTerms}
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
