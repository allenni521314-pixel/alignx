import { useState } from "react";
import { ClipboardCheck, ArrowRight, AlertCircle, Check, ShieldAlert } from "lucide-react";
import { analyzePrelaunch, PrelaunchCheck as PC } from "@/lib/api";

export default function PrelaunchCheck() {
  const [step, setStep] = useState(1);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<PC | null>(null);

  // Form state
  const [productName, setProductName] = useState("");
  const [titleDraft, setTitleDraft] = useState("");
  const [highlights, setHighlights] = useState("");
  const [bullets, setBullets] = useState(["", "", "", "", ""]);

  const handleAnalyze = async () => {
    if (!productName.trim()) return;
    setAnalyzing(true);
    try {
      const res = await analyzePrelaunch({
        product_name: productName,
        title_draft: titleDraft,
        key_highlights: highlights,
        bullet_1: bullets[0],
        bullet_2: bullets[1],
        bullet_3: bullets[2],
        bullet_4: bullets[3],
        bullet_5: bullets[4],
      });
      setResult(res);
      setStep(3);
    } finally {
      setAnalyzing(false);
    }
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case "通过": return <Check size={16} className="text-[#34c759]" />;
      case "需修改": return <AlertCircle size={16} className="text-[#ff9500]" />;
      default: return <ShieldAlert size={16} className="text-[#ff3b30]" />;
    }
  };

  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">上架准入</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          上传 Listing 素材，逐位置诊断是否达到上架标准
        </p>
      </div>

      {/* Steps indicator */}
      <div className="flex items-center gap-3 mb-8">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-3">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-[14px] font-medium transition-all ${
                step >= s ? "bg-[#0071e3] text-white" : "bg-[#e8e8ed] text-[#86868b]"
              }`}
            >
              {s}
            </div>
            {s < 3 && (
              <div className={`w-8 h-0.5 rounded ${step > s ? "bg-[#0071e3]" : "bg-[#e8e8ed]"}`} />
            )}
          </div>
        ))}
        <span className="text-[14px] text-[#86868b] ml-2">
          {step === 1 ? "填写素材" : step === 2 ? "分析中" : "诊断结果"}
        </span>
      </div>

      {/* Step 1: Input */}
      {step === 1 && (
        <div className="space-y-4">
          <div className="apple-card p-6 space-y-4">
            <Field label="产品名称" value={productName} onChange={setProductName} placeholder="如：光触媒 USB-C 宠物除臭器" />
            <Field label="标题草案" value={titleDraft} onChange={setTitleDraft} placeholder="Amazon 产品标题" />

            <div>
              <label className="block text-[13px] font-medium text-[#86868b] mb-2">亮点</label>
              <input
                value={highlights}
                onChange={(e) => setHighlights(e.target.value)}
                placeholder="一句话核心卖点"
                className="apple-input"
              />
            </div>

            <div>
              <label className="block text-[13px] font-medium text-[#86868b] mb-2">五点描述</label>
              <div className="space-y-2">
                {bullets.map((b, i) => (
                  <input
                    key={i}
                    value={b}
                    onChange={(e) => {
                      const next = [...bullets];
                      next[i] = e.target.value;
                      setBullets(next);
                    }}
                    placeholder={`第 ${i + 1} 点`}
                    className="apple-input"
                  />
                ))}
              </div>
            </div>
          </div>

          <div className="apple-card p-8 text-center">
            <p className="text-[14px] text-[#86868b] mb-2">主图 / 副图 / A+ 素材</p>
            <p className="text-[13px] text-[#86868b]/60">拖拽上传 或 点击选择文件</p>
          </div>

          <button
            onClick={handleAnalyze}
            disabled={!productName.trim()}
            className="apple-btn-primary flex items-center gap-2 px-8 py-3 text-[16px]"
          >
            <ClipboardCheck size={18} />
            开始准入检查
            <ArrowRight size={16} />
          </button>
        </div>
      )}

      {/* Step 2: Loading */}
      {step === 2 && !result && (
        <div className="apple-card p-16 text-center">
          <div className="w-10 h-10 border-2 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mx-auto mb-4" />
          <p className="text-[17px] text-[#86868b]">
            {analyzing ? "AI 正在逐位置诊断..." : "准备中"}
          </p>
        </div>
      )}

      {/* Step 3: Result */}
      {result && (
        <div className="space-y-4">
          {/* Overall verdict */}
          <div className="apple-card p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                result.admission_result === "可以上架" ? "bg-[#34c759]/10" :
                result.admission_result === "谨慎上架" ? "bg-[#ff9500]/10" :
                "bg-[#ff3b30]/10"
              }`}>
                {result.admission_result === "可以上架" ? (
                  <Check size={20} className="text-[#34c759]" />
                ) : result.admission_result === "谨慎上架" ? (
                  <AlertCircle size={20} className="text-[#ff9500]" />
                ) : (
                  <ShieldAlert size={20} className="text-[#ff3b30]" />
                )}
              </div>
              <div>
                <p className="text-[20px] font-semibold">{result.admission_result}</p>
                {result.conclusion && (
                  <p className="text-[14px] text-[#86868b] mt-0.5">{result.conclusion}</p>
                )}
              </div>
            </div>
          </div>

          {/* Position diagnoses */}
          {result.position_diagnoses_json && result.position_diagnoses_json.length > 0 && (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">
                逐位置诊断
              </h3>
              <div className="space-y-3">
                {result.position_diagnoses_json.map((d, i) => (
                  <div
                    key={i}
                    className={`rounded-xl p-4 border transition-colors ${
                      d.status === "通过" ? "bg-[#34c759]/[0.04] border-[#34c759]/20" :
                      d.status === "需修改" ? "bg-[#ff9500]/[0.04] border-[#ff9500]/20" :
                      "bg-[#ff3b30]/[0.04] border-[#ff3b30]/20"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      {statusIcon(d.status)}
                      <span className="text-[14px] font-semibold">{d.position_name}</span>
                      <span className="text-[12px] text-[#86868b]">{d.position_type}</span>
                    </div>
                    {d.issue && <p className="text-[14px] mb-1">{d.issue}</p>}
                    {d.recommendation && (
                      <p className="text-[13px] text-[#0071e3] bg-[#0071e3]/[0.06] rounded-lg p-2 mt-2">
                        {d.recommendation}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div>
      <label className="block text-[13px] font-medium text-[#86868b] mb-2">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="apple-input"
      />
    </div>
  );
}
