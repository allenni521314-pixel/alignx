import { useState } from "react";
import { ClipboardCheck, Upload } from "lucide-react";
import { analyzePrelaunch, PrelaunchCheck as PC } from "@/lib/api";

export default function PrelaunchCheck() {
  const [productName, setProductName] = useState("");
  const [titleDraft, setTitleDraft] = useState("");
  const [highlights, setHighlights] = useState("");
  const [bullets, setBullets] = useState(["", "", "", "", ""]);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<PC | null>(null);

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
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">上架准入</h1>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">产品名称</label>
          <input
            type="text"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">标题草案</label>
          <input
            type="text"
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">亮点</label>
          <input
            type="text"
            value={highlights}
            onChange={(e) => setHighlights(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">五点描述</label>
          {bullets.map((b, i) => (
            <input
              key={i}
              type="text"
              value={b}
              onChange={(e) => {
                const next = [...bullets];
                next[i] = e.target.value;
                setBullets(next);
              }}
              placeholder={`第 ${i + 1} 点`}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 mb-2"
            />
          ))}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">素材上传（主图 / 副图 / A+）</label>
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center text-gray-400">
            <Upload className="mx-auto mb-2" size={24} />
            拖拽或点击上传图片素材
          </div>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={analyzing || !productName.trim()}
          className="px-6 py-2.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
        >
          <ClipboardCheck size={18} />
          {analyzing ? "分析中..." : "准入检查"}
        </button>
      </div>

      {result && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4">准入结果：{result.admission_result}</h2>
          <p className="text-gray-600">{result.conclusion}</p>
        </div>
      )}
    </div>
  );
}
