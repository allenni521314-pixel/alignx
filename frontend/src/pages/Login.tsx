import { useState } from "react";
import { Shield, Mail, Building, Key, ArrowRight } from "lucide-react";

const API = "/api/v1/auth";

export default function Login() {
  const [email, setEmail] = useState("");
  const [storeName, setStoreName] = useState("");
  const [code, setCode] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [devCode, setDevCode] = useState("");
  const [error, setError] = useState("");

  const handleSend = async () => {
    if (!email) return;
    setSending(true); setError("");
    try {
      const res = await fetch(`${API}/send-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (data.code) { setDevCode(data.code); setSent(true); }
      else { setError(data.detail || "发送失败"); }
    } catch { setError("网络错误"); }
    finally { setSending(false); }
  };

  const handleLogin = async () => {
    if (!email || !code) return;
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API}/verify-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code, store_name: storeName }),
      });
      const data = await res.json();
      if (data.success) {
        localStorage.setItem("alignx_token", data.token);
        localStorage.setItem("alignx_user", JSON.stringify({ id: data.user_id, email: data.email, store_name: data.store_name }));
        window.location.href = "/";
      } else {
        setError(data.detail || "验证失败");
      }
    } catch { setError("网络错误"); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[#f5f5f7] flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-[#0071e3] rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Shield size={24} className="text-white" />
          </div>
          <h1 className="text-[28px] font-bold tracking-[-0.025em] mb-1">AlignX</h1>
          <p className="text-[14px] text-[#86868b]">先验证 · 再投入</p>
        </div>

        {/* Form */}
        <div className="apple-card p-6 space-y-4">
          {/* Store Name */}
          <div>
            <label className="flex items-center gap-2 text-[13px] font-medium text-[#86868b] mb-2">
              <Building size={14} />
              店铺名称
            </label>
            <input
              value={storeName}
              onChange={(e) => setStoreName(e.target.value)}
              placeholder="输入店铺名称或公司名"
              className="apple-input"
            />
          </div>

          {/* Email */}
          <div>
            <label className="flex items-center gap-2 text-[13px] font-medium text-[#86868b] mb-2">
              <Mail size={14} />
              邮箱
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="输入邮箱地址"
              className="apple-input"
            />
          </div>

          {/* Code */}
          <div>
            <label className="flex items-center gap-2 text-[13px] font-medium text-[#86868b] mb-2">
              <Key size={14} />
              验证码
            </label>
            <div className="flex gap-2">
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="6位验证码"
                maxLength={6}
                className="apple-input flex-1"
              />
              <button
                onClick={handleSend}
                disabled={!email || sending}
                className="apple-btn-secondary text-[13px] px-4 py-2 whitespace-nowrap"
              >
                {sending ? "发送中..." : sent ? "重新发送" : "发送验证码"}
              </button>
            </div>
          </div>

          {/* Dev: show code */}
          {devCode && (
            <div className="bg-[#ff9500]/[0.06] rounded-xl p-3 text-center">
              <p className="text-[12px] text-[#86868b]">开发模式 · 验证码</p>
              <p className="text-[20px] font-bold tracking-[0.2em] text-[#ff9500]">{devCode}</p>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-[#ff3b30]/[0.06] rounded-xl p-3 text-center">
              <p className="text-[13px] text-[#ff3b30]">{error}</p>
            </div>
          )}

          {/* Submit */}
          <button
            onClick={handleLogin}
            disabled={!email || !code || loading}
            className="apple-btn-primary w-full py-3 flex items-center justify-center gap-2 text-[16px]"
          >
            {loading ? "验证中..." : "进入工作台"} <ArrowRight size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
