import { useState } from "react";
import { Shield, Mail, Building, Key, ArrowRight } from "lucide-react";
import { sendLoginCode, verifyLoginCode } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function Login() {
  const { t, language, setLanguage } = useI18n();
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
      const data = await sendLoginCode(email);
      if (data.code) { setDevCode(data.code); setSent(true); }
      else { setError(data.detail || t("login.sendFailed")); }
    } catch (e) { setError(e instanceof Error ? e.message : t("common.networkError")); }
    finally { setSending(false); }
  };

  const handleLogin = async () => {
    if (!email || !code) return;
    setLoading(true); setError("");
    try {
      const data = await verifyLoginCode({ email, code, store_name: storeName });
      if (data.success) {
        localStorage.setItem("alignx_token", data.token);
        localStorage.setItem("alignx_user", JSON.stringify({ id: data.user_id, email: data.email, store_name: data.store_name }));
        window.location.href = "/today-decisions";
      } else {
        setError(data.detail || t("login.verifyFailed"));
      }
    } catch (e) { setError(e instanceof Error ? e.message : t("common.networkError")); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[#fbfaf7] flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">
        <div className="mb-5 flex justify-end">
          <select
            value={language}
            onChange={(event) => setLanguage(event.target.value === "en" ? "en" : "zh")}
            className="rounded-full border border-[#d2d2d7] bg-white px-3 py-1.5 text-[13px] text-[#1d1d1f]"
            aria-label={t("language.label")}
          >
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </div>
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-[#0F2A24] rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Shield size={24} className="text-white" />
          </div>
          <h1 className="text-[28px] font-bold tracking-[-0.025em] mb-1">{t("login.title")}</h1>
        </div>

        {/* Form */}
        <div className="apple-card p-6 space-y-4">
          {/* Store Name */}
          <div>
            <label className="flex items-center gap-2 text-[13px] font-medium text-[#86868b] mb-2">
              <Building size={14} />
              {t("login.storeName")}
            </label>
            <input
              value={storeName}
              onChange={(e) => setStoreName(e.target.value)}
              placeholder={t("login.storePlaceholder")}
              className="apple-input"
            />
          </div>

          {/* Email */}
          <div>
            <label className="flex items-center gap-2 text-[13px] font-medium text-[#86868b] mb-2">
              <Mail size={14} />
              {t("login.email")}
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("login.emailPlaceholder")}
              className="apple-input"
            />
          </div>

          {/* Code */}
          <div>
            <label className="flex items-center gap-2 text-[13px] font-medium text-[#86868b] mb-2">
              <Key size={14} />
              {t("login.code")}
            </label>
            <div className="flex gap-2">
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder={t("login.codePlaceholder")}
                maxLength={6}
                className="apple-input flex-1"
              />
              <button
                onClick={handleSend}
                disabled={!email || sending}
                className="apple-btn-secondary text-[13px] px-4 py-2 whitespace-nowrap"
              >
                {sending ? t("login.sending") : sent ? t("login.resend") : t("login.sendCode")}
              </button>
            </div>
          </div>

          {/* Dev: show code */}
          {devCode && (
            <div className="bg-[#ff9500]/[0.06] rounded-xl p-3 text-center">
              <p className="text-[12px] text-[#86868b]">{t("login.devCode")}</p>
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
            {loading ? t("login.verifying") : t("login.enterWorkspace")} <ArrowRight size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
