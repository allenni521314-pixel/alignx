import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck, ArrowRight, AlertCircle, Check, ShieldAlert, Upload } from "lucide-react";
import { analyzePrelaunch, listPrelaunchChecks, PrelaunchCheck as PC, type PositionDiagnosis } from "@/lib/api";

const SAVE_KEY = "alignx_prelaunch_draft";
const METRIC_LABELS: Record<string, string> = {
  CTR: "点击率",
  CVR: "转化率",
  ACOS: "ACOS",
  CPC: "CPC",
  "Add to Cart": "加购率",
  "Session%": "会话占比",
};

function metricLabel(value: string) {
  return METRIC_LABELS[value] || value || "暂无";
}

function loadDraft() { try { const r = localStorage.getItem(SAVE_KEY); return r ? JSON.parse(r) : null; } catch { return null; } }
function saveDraft(d: Record<string, unknown>) { try { localStorage.setItem(SAVE_KEY, JSON.stringify(d)); } catch { console.warn("自动保存失败：存储空间不足，请清理浏览器缓存。"); } }

export default function PrelaunchCheck() {
  const draft = loadDraft();
  const [step, setStep] = useState(1);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PC | null>(null);
  const [images, setImages] = useState<{ name: string; url: string; slot: string }[]>(draft?.images ?? []);
  const [productName, setProductName] = useState(draft?.productName ?? "");
  const [titleDraft, setTitleDraft] = useState(draft?.titleDraft ?? "");
  const [highlights, setHighlights] = useState(draft?.highlights ?? "");
  const [bullets, setBullets] = useState(draft?.bullets ?? ["", "", "", "", ""]);
  const savedRef = useRef(false);
  const { data: history, refetch: refetchHistory } = useQuery({
    queryKey: ["prelaunch-check-history"],
    queryFn: () => listPrelaunchChecks(1),
  });

  const restoreFromHistory = (item: PC) => {
    const restoredImages = imagesFromHistory(item);
    setProductName(item.product_name || "");
    setTitleDraft(item.title_draft || "");
    setHighlights(item.key_highlights || "");
    setBullets([item.bullet_1 || "", item.bullet_2 || "", item.bullet_3 || "", item.bullet_4 || "", item.bullet_5 || ""]);
    setImages(restoredImages);
    saveDraft({
      productName: item.product_name || "",
      titleDraft: item.title_draft || "",
      highlights: item.key_highlights || "",
      bullets: [item.bullet_1 || "", item.bullet_2 || "", item.bullet_3 || "", item.bullet_4 || "", item.bullet_5 || ""],
      images: restoredImages,
    });
    setResult(item);
    setStep(4);
  };

  useEffect(() => {
    if (!savedRef.current) { savedRef.current = true; return; }
    const t = setTimeout(() => saveDraft({ productName, titleDraft, highlights, bullets, images }), 500);
    return () => clearTimeout(t);
  }, [productName, titleDraft, highlights, bullets, images]);

  const handleAnalyze = () => { if (!productName.trim()) return; setStep(2); };

  const handleConfirm = async () => {
    setAnalyzing(true); setStep(3);
    try {
      const imgData: { slot: string; name: string; base64: string }[] = images.map(img => ({
        slot: img.slot,
        name: img.name,
        base64: img.url.includes('base64,') ? img.url.split('base64,')[1] : img.url.split(',')[1],
      }));
      const res = await analyzePrelaunch({
        product_name: productName, title_draft: titleDraft, key_highlights: highlights,
        bullet_1: bullets[0], bullet_2: bullets[1], bullet_3: bullets[2], bullet_4: bullets[3], bullet_5: bullets[4],
        image_count: images.length, image_slots: imgData,
      });
      setResult(res); setStep(4);
      refetchHistory();
    } catch (e: any) { setError(e.message || "分析失败"); setStep(3); }
    finally { setAnalyzing(false); }
  };

  const statusIcon = (s: string) => {
    switch (s) {
      case "通过": return <Check size={16} className="text-[#34c759]" />;
      case "需修改": return <AlertCircle size={16} className="text-[#ff9500]" />;
      case "待识别": return <AlertCircle size={16} className="text-[#86868b]" />;
      default: return <ShieldAlert size={16} className="text-[#ff3b30]" />;
    }
  };

  return (
    <div className="max-w-[760px] mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">上架准入</h1>
        <p className="text-[17px] text-[#86868b]">上传 Listing 素材，逐位置诊断是否达到上架标准</p>
      </div>
      <div className="flex items-center gap-3 mb-8">
        {[1,2,3,4].map(s => (
          <div key={s} className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-[14px] font-medium ${step>=s?"bg-[#0F2A24] text-white":"bg-[#e8e8ed] text-[#86868b]"}`}>{s}</div>
            {s<4 && <div className={`w-8 h-0.5 rounded ${step>s?"bg-[#0F2A24]":"bg-[#e8e8ed]"}`} />}
          </div>
        ))}
        <span className="text-[14px] text-[#86868b] ml-2">{step===1?"填写素材":step===2?"确认提交":step===3?"AI分析中":"诊断结果"}</span>
      </div>

      {step === 1 && (
        <div className="space-y-4">
          <div className="apple-card p-6 space-y-4">
            <Field label="产品名称" value={productName} onChange={setProductName} placeholder="如：光触媒 USB-C 宠物除臭器" />
            <Field label="标题草案" value={titleDraft} onChange={setTitleDraft} placeholder="Amazon 产品标题" />
            <Field label="亮点" value={highlights} onChange={setHighlights} placeholder="一句话核心卖点" />
            <div><label className="block text-[13px] font-medium text-[#86868b] mb-2">五点描述</label><div className="space-y-2">{bullets.map((b:string,i:number)=><Field key={i} value={b} onChange={v=>{const n=[...bullets];n[i]=v;setBullets(n)}} placeholder={`第${i+1}点`} />)}</div></div>
          </div>
          <ImageSlots images={images} setImages={setImages} />
          <button onClick={handleAnalyze} disabled={!productName.trim()} className="apple-btn-primary flex items-center gap-2 px-8 py-3 text-[16px]"><ClipboardCheck size={18} />开始准入检查<ArrowRight size={16} /></button>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <div className="apple-card p-6"><h3 className="text-[15px] font-semibold mb-4">确认提交内容</h3>
            <div className="space-y-3 text-[14px]">
              <div><span className="text-[#86868b]">产品名称：</span>{productName}</div>
              <div><span className="text-[#86868b]">标题：</span>{titleDraft||"未填"}</div>
              <div><span className="text-[#86868b]">亮点：</span>{highlights||"未填"}</div>
              <div><span className="text-[#86868b]">图片：</span>{images.length>0?`${images.length}张`:"未上传"}</div>
            </div>
          </div>
          <div className="flex gap-3"><button onClick={()=>setStep(1)} className="apple-btn-secondary px-6 py-3">返回修改</button><button onClick={handleConfirm} className="apple-btn-primary flex items-center gap-2 px-6 py-3"><ClipboardCheck size={18} />确认提交</button></div>
        </div>
      )}

      {step === 3 && !result && (
        <div className="apple-card p-16 text-center">
          {error ? <><ShieldAlert size={32} className="text-[#ff3b30] mx-auto mb-3" /><p className="text-[17px] text-[#ff3b30]">分析失败</p><p className="text-[14px] text-[#86868b] mt-2">{error}</p><button onClick={()=>{setError(null);setStep(1)}} className="apple-btn-primary mt-4 px-6 py-2">← 返回重试</button></> : <><div className="w-10 h-10 border-2 border-[#0F2A24]/20 border-t-[#0F2A24] rounded-full animate-spin mx-auto mb-4" /><p className="text-[17px] text-[#86868b]">AI 正在逐位置诊断...</p></>}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="flex gap-3 mb-2"><button onClick={()=>{setStep(1);setResult(null)}} className="apple-btn-secondary text-[14px] px-4 py-2">← 重新修改</button></div>
          <div className="apple-card p-6"><div className="flex items-center gap-3 mb-3"><div className={`w-10 h-10 rounded-full flex items-center justify-center ${result.admission_result==="可以上架"?"bg-[#34c759]/10":result.admission_result==="谨慎上架"?"bg-[#ff9500]/10":"bg-[#ff3b30]/10"}`}>{result.admission_result==="可以上架"?<Check size={20} className="text-[#34c759]"/>:result.admission_result==="谨慎上架"?<AlertCircle size={20} className="text-[#ff9500]"/>:<ShieldAlert size={20} className="text-[#ff3b30]"/>}</div><div><p className="text-[20px] font-semibold">{result.admission_result}</p>{result.conclusion&&<p className="text-[14px] text-[#86868b] mt-0.5">{result.conclusion}</p>}</div></div></div>
          {(result.position_diagnoses_json?.length ?? 0) > 0 && (
            <div className="apple-card p-6"><h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">逐位置诊断</h3><div className="space-y-3">{(result.position_diagnoses_json ?? []).map((d,i)=><DiagnosisItem key={i} diagnosis={d} statusIcon={statusIcon} />)}</div></div>
          )}
        </div>
      )}
      {!result && history?.items && history.items.length > 0 && (
        <div className="apple-card p-6 mt-6">
          <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">历史记录</h3>
          <div className="space-y-3">
            {history.items.slice(0, 6).map((item) => (
              <button
                key={item.id}
                onClick={() => restoreFromHistory(item)}
                className="w-full text-left rounded-xl border border-[#d2d2d7]/70 bg-white/70 p-4 hover:border-[#0F2A24]/30 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[14px] font-semibold text-[#1d1d1f] truncate">{item.product_name || "暂无"}</p>
                    <p className="text-[12px] text-[#86868b] mt-1 truncate">{item.conclusion || "暂无"}</p>
                  </div>
                  <span className={`shrink-0 text-[12px] px-2 py-1 rounded-full ${
                    item.admission_result === "可以上架"
                      ? "bg-[#34c759]/10 text-[#34c759]"
                      : item.admission_result === "谨慎上架"
                      ? "bg-[#ff9500]/10 text-[#ff9500]"
                      : "bg-[#ff3b30]/10 text-[#ff3b30]"
                  }`}>{item.admission_result || "暂无"}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function imagesFromHistory(item: PC): { name: string; url: string; slot: string }[] {
  const images: { name: string; url: string; slot: string }[] = [];
  const push = (slot: string, url?: string | null) => {
    if (url) images.push({ slot, url, name: slot });
  };
  push("main", item.main_image_path);
  push("img2", item.image_2_path);
  push("img3", item.image_3_path);
  push("img4", item.image_4_path);
  push("img5", item.image_5_path);
  push("img6", item.image_6_path);
  push("img7", item.image_7_path);
  for (const image of item.aplus_images_json || []) {
    if (image?.slot && image?.url) {
      images.push({ slot: image.slot, url: image.url, name: image.name || image.slot });
    }
  }
  return images;
}

function Field({label,value,onChange,placeholder}:{label?:string;value:string;onChange:(v:string)=>void;placeholder:string}){
  const ref=useRef<HTMLTextAreaElement|null>(null);
  useEffect(()=>{const el=ref.current;if(!el)return;el.style.height="auto";el.style.height=`${el.scrollHeight}px`;},[value]);
  return <div>{label&&<label className="block text-[13px] font-medium text-[#86868b] mb-2">{label}</label>}<textarea ref={ref} rows={1} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder} className="apple-input min-h-[48px] resize-none overflow-hidden leading-[1.45]" /></div>
}

function DiagnosisItem({diagnosis:d,statusIcon}:{diagnosis:PositionDiagnosis;statusIcon:(s:string)=>React.ReactNode}){
  const [copied,setCopied]=useState(false);
  const metrics = d.impact_metrics ?? [];
  const hasSuggestion=d.recommendation&&d.status!=="通过";
  const ocrPending = d.uploaded === true && (d.ocr_status === "pending" || d.ocr_status === "failed");
  const sc=d.final_score!=null?(d.final_score>=4?"text-[#34c759]":d.final_score>=3?"text-[#ff9500]":"text-[#ff3b30]"):"text-[#86868b]";
  const cardClass = ocrPending
    ? "bg-[#86868b]/[0.04] border-[#86868b]/20"
    : d.status==="通过"
    ? "bg-[#34c759]/[0.04] border-[#34c759]/20"
    : d.status==="需修改"
    ? "bg-[#ff9500]/[0.04] border-[#ff9500]/20"
    : "bg-[#ff3b30]/[0.04] border-[#ff3b30]/20";
  const badgeClass = ocrPending
    ? "bg-[#86868b]/10 text-[#86868b]"
    : d.final_score!=null&&d.final_score>=4
    ? "bg-[#34c759]/10 text-[#34c759]"
    : d.final_score!=null&&d.final_score>=3
    ? "bg-[#ff9500]/10 text-[#ff9500]"
    : "bg-[#ff3b30]/10 text-[#ff3b30]";
  return <div className={`rounded-xl p-4 border ${cardClass}`}>
    <div className="flex items-center gap-2 mb-2">{statusIcon(d.status)}<span className="text-[14px] font-semibold">{d.position_name}</span>{ocrPending?<span className="ml-auto text-[13px] font-bold text-[#86868b]">待识别</span>:d.final_score!=null&&<span className={`ml-auto text-[13px] font-bold ${sc}`}>{d.final_score.toFixed(1)}</span>}{d.usable_status&&d.status!=="通过"&&<span className={`text-[11px] px-1.5 py-0.5 rounded-full ${badgeClass}`}>{d.usable_status}</span>}</div>
    {d.issue&&<p className="text-[14px] mb-1">{d.issue}</p>}
    {metrics.length>0&&<div className="flex items-center gap-2 mb-2"><span className="text-[11px] text-[#86868b]">影响指标</span>{metrics.map((m:string,i:number)=><span key={i} className="text-[11px] px-1.5 py-0.5 rounded-full bg-[#0F2A24]/[0.06] text-[#0F2A24]">{metricLabel(m)}</span>)}</div>}
    {hasSuggestion&&<div className="mt-2"><div className="bg-[#fbfaf7] rounded-lg p-3 flex items-start justify-between gap-3"><div className="flex-1 min-w-0"><p className="text-[11px] text-[#86868b] mb-1">{ocrPending?"规则参考（未读取图片内容）":"修改建议"}</p><p className="text-[13px] text-[#0F2A24]">{d.recommendation}</p></div><button onClick={()=>{navigator.clipboard.writeText(d.recommendation||"");setCopied(true);setTimeout(()=>setCopied(false),2000)}} className="shrink-0 px-3 py-1.5 rounded-lg bg-[#0F2A24] text-white text-[12px] hover:bg-[#173a32] transition-colors">{copied?"已复制":"复制"}</button></div></div>}
  </div>;
}

function ImageSlots({images,setImages}:{images:{name:string;url:string;slot:string}[];setImages:(imgs:{name:string;url:string;slot:string}[])=>void}){
  const compressImage = (dataUrl: string): Promise<string> => new Promise(resolve => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const maxW = 512;
      const scale = Math.min(1, maxW / img.width);
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      canvas.getContext('2d')!.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL('image/jpeg', 0.6));
    };
    img.src = dataUrl;
  });
  const up=(slot:string)=>(e:React.ChangeEvent<HTMLInputElement>)=>{const f=e.target.files?.[0];if(!f)return;const r=new FileReader();r.onload=async()=>{const compressed=await compressImage(r.result as string);setImages(images.filter(i=>i.slot!==slot).concat({name:f.name,url:compressed,slot}));};r.readAsDataURL(f);};
  const rm=(slot:string)=>setImages(images.filter(i=>i.slot!==slot));
  const get=(slot:string)=>images.find(i=>i.slot===slot);
  const slots=[{s:"main",l:"主图",f:"搜索结果第一视觉",r:"纯白底·仅产品·无文字logo"},{s:"img2",l:"副图2",f:"核心卖点可视化",r:"图标+短句"},{s:"img3",l:"副图3",f:"使用场景展示",r:"真实环境"},{s:"img4",l:"副图4",f:"尺寸规格对比",r:"参照物+标注"},{s:"img5",l:"副图5",f:"功能细节演示",r:"特写/步骤"},{s:"img6",l:"副图6",f:"信任背书",r:"认证/质保/包装"},{s:"img7",l:"副图7",f:"场景氛围",r:"生活方式"}];
  const aplus=[{s:"aplus1",l:"A+1",f:"品牌主视觉"},{s:"aplus2",l:"A+2",f:"差异化对比"},{s:"aplus3",l:"A+3",f:"卖点1·左图右文"},{s:"aplus4",l:"A+4",f:"卖点2"},{s:"aplus5",l:"A+5",f:"卖点3"},{s:"aplus6",l:"A+6",f:"技术规格参数"},{s:"aplus7",l:"A+7",f:"场景详解"},{s:"aplus8",l:"A+8",f:"认证质保"},{s:"aplus9",l:"A+9",f:"FAQ+售后"}];
  return <div className="space-y-3">
    <div className="apple-card p-5"><h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">主图 & 副图</h3><div className="grid grid-cols-4 gap-3">{slots.map(s=><Slot key={s.s} slot={s.s} label={s.l} func={s.f} rule={s.r} img={get(s.s)} up={up(s.s)} rm={()=>rm(s.s)}/>)}</div></div>
    <div className="apple-card p-5"><h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">A+ 内容（最多9张）</h3><div className="grid grid-cols-5 gap-3">{aplus.map(s=><Slot key={s.s} slot={s.s} label={s.l} func={s.f} img={get(s.s)} up={up(s.s)} rm={()=>rm(s.s)}/>)}</div></div>
  </div>;
}

function Slot({slot,label,func,rule,img,up,rm}:{slot:string;label:string;func:string;rule?:string;img?:{name:string;url:string};up:(e:React.ChangeEvent<HTMLInputElement>)=>void;rm:()=>void}){
  const [dr,setDr]=useState(false);
  const id=`slot-${slot}`;
  return <div><input id={id} type="file" accept="image/*" className="hidden" onChange={up}/><label htmlFor={id} onDragOver={e=>{e.preventDefault();setDr(true)}} onDragLeave={()=>setDr(false)} onDrop={e=>{e.preventDefault();setDr(false);const f=e.dataTransfer.files?.[0];if(f&&f.type.startsWith("image/"))up({target:{files:e.dataTransfer.files}}as any)}} className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed cursor-pointer transition-colors h-[88px] ${img?"border-[#34c759]/40 bg-[#34c759]/[0.03]":dr?"border-[#0F2A24] bg-[#0F2A24]/[0.05]":"border-[#d2d2d7] hover:border-[#0F2A24]/40 hover:bg-[#0F2A24]/[0.02]"}`}>{img?<div className="relative w-full h-full"><img src={img.url} alt={img.name} className="w-full h-full object-cover rounded-lg"/><button onClick={e=>{e.preventDefault();rm()}} className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-[#ff3b30] text-white rounded-full text-[8px] flex items-center justify-center">×</button></div>:<span className="text-[11px] font-medium text-[#86868b]">{label}</span>}</label><p className="text-[10px] text-[#86868b] mt-1 text-center">{func}</p>{rule&&!img&&<p className="text-[9px] text-[#86868b]/60 text-center">{rule}</p>}</div>;
}
