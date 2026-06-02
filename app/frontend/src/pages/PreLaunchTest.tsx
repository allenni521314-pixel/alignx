import { useState, useRef, useCallback, useEffect } from "react";
import { AppSidebar } from "@/components/AppSidebar";
import { PageHeader } from "@/components/PageHeader";
import { NextStepActions } from "@/components/NextStepActions";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { getAuthHeaders } from "@/lib/auth-headers";
import { toast } from "sonner";
import { saveActionSnapshot } from "@/lib/workflow-api";
import { finishModuleTask, removeModuleTask, upsertModuleTask } from "@/lib/module-task-store";
import jsPDF from "jspdf";
import {
  ClipboardCheck,
  Loader2,
  Sparkles,
  Type,
  ImageIcon,
  FileText,
  List,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  TrendingUp,
  Upload,
  X,
  Save,
  History,
  Download,
  Trash2,
  ChevronLeft,
  Search,
  Clock,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface DimensionScore {
  score: number;
  analysis: string;
  suggestions: string[];
  recommended_text?: string;
  validation_hypothesis?: string;
  attribution_metric?: string;
  validation_keywords?: string[];
  failed_scale?: string[];
  current_gap?: string;
  recommended_change?: string;
}

interface ScoringResult {
  title_keywords: DimensionScore;
  main_image: DimensionScore;
  a_plus_description: DimensionScore;
  bullet_points: DimensionScore;
  backend_keywords: DimensionScore;
  overall_score: number;
  overall_summary: string;
  cosmo_alignment: string;
  rufus_alignment: string;
  ordered_first_fixes?: string[];
  rule_context?: Record<string, unknown>;
  vision_alignment?: Record<string, unknown>;
  product_attribute_profile?: Record<string, unknown>;
  prelaunch_modification_plan?: Record<string, unknown>;
  ad_validation_alignment?: Record<string, unknown>;
  ad_validation_plan?: Record<string, unknown>;
}

interface HistoryItem {
  id: number;
  title: string;
  overall_score: number;
  score_title_keywords: number;
  score_main_image: number;
  score_a_plus: number;
  score_bullet_points: number;
  has_images: number;
  created_at: string | null;
}

interface HistoryDetail {
  id: number;
  title: string;
  keywords: string;
  bullet_points: string;
  a_plus_desc: string;
  overall_score: number;
  score_title_keywords: number;
  score_main_image: number;
  score_a_plus: number;
  score_bullet_points: number;
  overall_summary: string;
  cosmo_alignment: string;
  rufus_alignment: string;
  full_report: Record<string, unknown>;
  has_images: number;
  created_at: string | null;
}

type PrelaunchDimensionKey = "title_keywords" | "main_image" | "a_plus_description" | "bullet_points" | "backend_keywords";

/* ------------------------------------------------------------------ */
/*  Image helpers                                                      */
/* ------------------------------------------------------------------ */

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function isValidImageFile(file: File): boolean {
  return file.type.startsWith("image/") && file.size <= 10 * 1024 * 1024;
}

function buildLaunchReadiness(result: ScoringResult, keywords: string) {
  const dims = [
    { label: "标题/关键词", score: result.title_keywords.score, suggestions: result.title_keywords.suggestions },
    { label: "主图/副图", score: result.main_image.score, suggestions: result.main_image.suggestions },
    { label: "A+内容", score: result.a_plus_description.score, suggestions: result.a_plus_description.suggestions },
    { label: "五点描述", score: result.bullet_points.score, suggestions: result.bullet_points.suggestions },
    { label: "后台关键词", score: result.backend_keywords.score, suggestions: result.backend_keywords.suggestions },
  ];
  const weakDims = dims.filter((dim) => dim.score < 70);
  const riskLevel = result.overall_score >= 80 && weakDims.length === 0
    ? "低"
    : result.overall_score >= 65
      ? "中"
      : "高";
  const launchAdvice = riskLevel === "低" ? "建议上架" : riskLevel === "中" ? "修改后上架" : "暂缓上架";
  const mustFix = weakDims.flatMap((dim) =>
    (dim.suggestions.length ? dim.suggestions : [`补强${dim.label}`]).slice(0, 2)
  ).slice(0, 5);
  const keywordList = keywords.split(/[,，\n]/).map((k) => k.trim()).filter(Boolean);
  const missingKeywords = keywordList.length < 5
    ? ["核心类目词", "高意图场景词", "痛点/用途长尾词"].slice(0, 3 - Math.min(keywordList.length, 2))
    : [];
  const mismatchPoints = [
    result.cosmo_alignment,
    result.rufus_alignment,
    result.main_image.analysis,
  ].filter(Boolean).slice(0, 3);

  return {
    launchAdvice,
    riskLevel,
    mustFix: mustFix.length ? mustFix : ["当前未发现必须阻断上架的问题"],
    missingKeywords: missingKeywords.length ? missingKeywords : ["暂无明显缺失，建议结合类目核心搜索词复核"],
    mismatchPoints: mismatchPoints.length ? mismatchPoints : ["暂无明显表达错配"],
    preLaunchActions: dims.flatMap((dim) => dim.suggestions.slice(0, 1)).filter(Boolean).slice(0, 4),
  };
}

/* ------------------------------------------------------------------ */
/*  API helpers                                                        */
/* ------------------------------------------------------------------ */

const API_BASE = "/api/v1/prelaunch-test";

async function apiSaveResult(data: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(data),
  });
  return res.json();
}

async function apiEvaluateLaunch(data: Record<string, unknown>): Promise<ScoringResult & { ai_called?: boolean; ai_model?: string; ai_error?: string }> {
  const res = await fetch(`${API_BASE}/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(data),
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(payload?.detail || "上新检测失败");
  }
  return payload;
}

async function apiGetHistory(skip = 0, limit = 50, search = "") {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (search) params.set("search", search);
  const res = await fetch(`${API_BASE}/history?${params}`, {
    headers: getAuthHeaders(),
  });
  return res.json();
}

async function apiGetDetail(id: number) {
  const res = await fetch(`${API_BASE}/history/${id}`, {
    headers: getAuthHeaders(),
  });
  return res.json();
}

async function apiDeleteResult(id: number) {
  const res = await fetch(`${API_BASE}/history/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  return res.json();
}

/* ------------------------------------------------------------------ */
/*  Score visual helpers                                               */
/* ------------------------------------------------------------------ */

function ScoreRing({ score, size = 64 }: { score: number; size?: number }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = score >= 80 ? "#22c55e" : score >= 60 ? "#eab308" : "#ef4444";

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={4} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth={4}
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-bold" style={{ color }}>{score}</span>
      </div>
    </div>
  );
}

function ScoreIcon({ score }: { score: number }) {
  if (score >= 80) return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
  if (score >= 60) return <AlertTriangle className="w-4 h-4 text-amber-600" />;
  return <XCircle className="w-4 h-4 text-red-600" />;
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? "text-emerald-600 bg-emerald-50" : score >= 60 ? "text-amber-600 bg-amber-50" : "text-red-600 bg-red-50";
  return <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${color}`}>{score}</span>;
}

/* ------------------------------------------------------------------ */
/*  Multi-Image Upload Component (Main Images - 7 max)                 */
/* ------------------------------------------------------------------ */

const MAX_MAIN_IMAGES = 7;

function MainImageUploadZone({
  images,
  onAdd,
  onRemove,
  onReorder,
}: {
  images: string[];
  onAdd: (files: File[]) => void;
  onRemove: (index: number) => void;
  onReorder: (from: number, to: number) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);

  const handleFiles = useCallback(
    (fileList: FileList) => {
      const remaining = MAX_MAIN_IMAGES - images.length;
      if (remaining <= 0) {
        toast.error(`最多上传 ${MAX_MAIN_IMAGES} 张主图`);
        return;
      }
      const validFiles: File[] = [];
      for (let i = 0; i < Math.min(fileList.length, remaining); i++) {
        if (isValidImageFile(fileList[i])) {
          validFiles.push(fileList[i]);
        } else {
          toast.error(`"${fileList[i].name}" 不是有效图片或超过10MB`);
        }
      }
      if (fileList.length > remaining) {
        toast.warning(`已达上限，仅添加前 ${remaining} 张`);
      }
      if (validFiles.length > 0) onAdd(validFiles);
    },
    [images.length, onAdd]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (dragIdx !== null) return; // reorder handled separately
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles, dragIdx]
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFiles(e.target.files);
      }
      e.target.value = "";
    },
    [handleFiles]
  );

  const handleItemDragStart = (idx: number) => {
    setDragIdx(idx);
  };

  const handleItemDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    if (dragIdx !== null && dragIdx !== idx) {
      setDragOverIdx(idx);
    }
  };

  const handleItemDrop = (idx: number) => {
    if (dragIdx !== null && dragIdx !== idx) {
      onReorder(dragIdx, idx);
    }
    setDragIdx(null);
    setDragOverIdx(null);
  };

  const handleItemDragEnd = () => {
    setDragIdx(null);
    setDragOverIdx(null);
  };

  return (
    <div className="space-y-2">
      {images.length > 0 && (
        <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
          {images.map((src, idx) => (
            <div
              key={idx}
              draggable
              onDragStart={() => handleItemDragStart(idx)}
              onDragOver={(e) => handleItemDragOver(e, idx)}
              onDrop={() => handleItemDrop(idx)}
              onDragEnd={handleItemDragEnd}
              className={`relative group aspect-square rounded-lg overflow-hidden border bg-gray-50 cursor-grab active:cursor-grabbing transition-all ${
                dragOverIdx === idx
                  ? "border-teal-400 ring-2 ring-teal-300 scale-105"
                  : dragIdx === idx
                    ? "opacity-50 border-gray-300"
                    : "border-gray-200"
              }`}
            >
              <img src={src} alt={`主图 ${idx + 1}`} className="w-full h-full object-cover" />
              <button
                type="button"
                onClick={() => onRemove(idx)}
                className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/70 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
              >
                <X className="w-3 h-3 text-white" />
              </button>
              <span className="absolute bottom-1 left-1 text-[9px] text-white/80 bg-black/50 px-1 rounded">
                {idx === 0 ? "主图" : idx + 1}
              </span>
            </div>
          ))}
        </div>
      )}

      {images.length < MAX_MAIN_IMAGES && (
        <div
          className={`
            relative rounded-lg border-2 border-dashed transition-all duration-200 cursor-pointer
            ${isDragging
              ? "border-teal-400 bg-teal-50"
              : "border-gray-200 bg-gray-50 hover:border-gray-300 hover:bg-gray-100"
            }
          `}
          onDragOver={(e) => { e.preventDefault(); if (dragIdx === null) setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
          <div className="flex flex-col items-center justify-center py-6 px-4">
            <div className={`
              w-10 h-10 rounded-xl flex items-center justify-center mb-2 transition-colors
              ${isDragging ? "bg-teal-100" : "bg-gray-100"}
            `}>
              <Upload className={`w-4 h-4 ${isDragging ? "text-teal-600" : "text-gray-500"}`} />
            </div>
            <p className="text-xs text-gray-500 mb-0.5">
              {isDragging ? "松开以上传图片" : "拖拽或点击上传产品主图"}
            </p>
            <p className="text-[10px] text-gray-400">
              已上传 {images.length}/{MAX_MAIN_IMAGES} 张 · 支持批量上传 · 拖拽图片可排序
            </p>
          </div>
        </div>
      )}

      {images.length > 0 && (
        <p className="text-[10px] text-teal-600/70 flex items-center gap-1">
          <CheckCircle2 className="w-3 h-3" /> 已上传 {images.length} 张主图，将按素材完整度和图文承接关系评分（第1张为主图）
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Multi-Image Upload Component (A+ Images)                           */
/* ------------------------------------------------------------------ */

const MAX_APLUS_IMAGES = 9;

function APlusImageUploadZone({
  images,
  onAdd,
  onRemove,
}: {
  images: string[];
  onAdd: (files: File[]) => void;
  onRemove: (index: number) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFiles = useCallback(
    (fileList: FileList) => {
      const remaining = MAX_APLUS_IMAGES - images.length;
      if (remaining <= 0) {
        toast.error(`最多上传 ${MAX_APLUS_IMAGES} 张A+图片`);
        return;
      }
      const validFiles: File[] = [];
      for (let i = 0; i < Math.min(fileList.length, remaining); i++) {
        if (isValidImageFile(fileList[i])) {
          validFiles.push(fileList[i]);
        } else {
          toast.error(`"${fileList[i].name}" 不是有效图片或超过10MB`);
        }
      }
      if (fileList.length > remaining) {
        toast.warning(`已达上限，仅添加前 ${remaining} 张`);
      }
      if (validFiles.length > 0) onAdd(validFiles);
    },
    [images.length, onAdd]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFiles(e.target.files);
      }
      e.target.value = "";
    },
    [handleFiles]
  );

  return (
    <div className="space-y-2">
      {images.length > 0 && (
        <div className="grid grid-cols-4 sm:grid-cols-9 gap-2">
          {images.map((src, idx) => (
            <div key={idx} className="relative group aspect-square rounded-lg overflow-hidden border border-gray-200 bg-gray-50">
              <img src={src} alt={`A+图片 ${idx + 1}`} className="w-full h-full object-cover" />
              <button
                type="button"
                onClick={() => onRemove(idx)}
                className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/70 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
              >
                <X className="w-3 h-3 text-white" />
              </button>
              <span className="absolute bottom-1 left-1 text-[9px] text-white/80 bg-black/50 px-1 rounded">
                {idx + 1}
              </span>
            </div>
          ))}
        </div>
      )}

      {images.length < MAX_APLUS_IMAGES && (
        <div
          className={`
            relative rounded-lg border-2 border-dashed transition-all duration-200 cursor-pointer
            ${isDragging
              ? "border-gold-400 bg-gold-50"
              : "border-gray-200 bg-gray-50 hover:border-gray-300 hover:bg-gray-100"
            }
          `}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
          <div className="flex flex-col items-center justify-center py-5 px-4">
            <div className={`
              w-10 h-10 rounded-xl flex items-center justify-center mb-2 transition-colors
              ${isDragging ? "bg-gold-100" : "bg-gray-50"}
            `}>
              <Upload className={`w-4 h-4 ${isDragging ? "text-gold-600" : "text-gray-500"}`} />
            </div>
            <p className="text-xs text-gray-500 mb-0.5">
              {isDragging ? "松开以上传图片" : "拖拽或点击上传A+图片"}
            </p>
            <p className="text-[10px] text-gray-600">
              已上传 {images.length}/{MAX_APLUS_IMAGES} 张 · 支持批量上传
            </p>
          </div>
        </div>
      )}

      {images.length > 0 && (
        <p className="text-[10px] text-gold-600/70 flex items-center gap-1">
          <CheckCircle2 className="w-3 h-3" /> 已上传 {images.length} 张A+图片，将按A+素材完整度和图文承接关系评分
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Dimension Card                                                     */
/* ------------------------------------------------------------------ */

function DimScoreCard({
  title,
  icon,
  dim,
  color,
  dimensionKey,
  onApplyFix,
}: {
  title: string;
  icon: React.ReactNode;
  dim: DimensionScore;
  color: string;
  dimensionKey: PrelaunchDimensionKey;
  onApplyFix: (dimension: PrelaunchDimensionKey, dim: DimensionScore) => void;
}) {
  const needsFix = dim.score < 80;
  return (
    <Card className="bg-white border-gray-200 p-4 sm:p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-lg ${color} flex items-center justify-center`}>
            {icon}
          </div>
          <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        </div>
        <ScoreRing score={dim.score} />
      </div>

      <p className="text-xs text-gray-500 leading-relaxed mb-3">{dim.analysis}</p>

      {(dim.failed_scale?.length || dim.current_gap || dim.recommended_change) && (
        <div className="mb-3 rounded-lg border border-amber-100 bg-amber-50/60 px-3 py-2">
          {dim.failed_scale && dim.failed_scale.length > 0 && (
            <p className="text-[10px] font-semibold text-amber-700">
              未过标准：{dim.failed_scale.join(" / ")}
            </p>
          )}
          {dim.current_gap && (
            <p className="mt-1 text-[11px] leading-relaxed text-gray-700">{dim.current_gap}</p>
          )}
          {dim.recommended_change && (
            <p className="mt-1 text-[11px] font-semibold leading-relaxed text-gray-900">{dim.recommended_change}</p>
          )}
        </div>
      )}

      {dim.suggestions.length > 0 && (
        <div className="space-y-1.5">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">优化建议</span>
          {dim.suggestions.map((s, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-gray-500">
              <ScoreIcon score={dim.score} />
              <span>{s}</span>
            </div>
          ))}
        </div>
      )}
      {(dim.validation_hypothesis || dim.attribution_metric) && (
        <div className="mt-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
          {dim.validation_hypothesis && (
            <p className="text-[11px] leading-relaxed text-gray-600">{dim.validation_hypothesis}</p>
          )}
          {dim.attribution_metric && (
            <p className="mt-1 text-[10px] font-semibold text-brand-600">归因指标：{dim.attribution_metric}</p>
          )}
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        {needsFix ? (
          <Button
            type="button"
            size="sm"
            onClick={() => onApplyFix(dimensionKey, dim)}
            className="h-8 bg-brand-600 hover:bg-brand-700 text-white"
          >
            按推荐回填
          </Button>
        ) : (
          <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">
            已达80分上架线
          </Badge>
        )}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  PDF Export                                                         */
/* ------------------------------------------------------------------ */

function generatePDF(result: ScoringResult, titleText: string) {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 15;
  const contentWidth = pageWidth - margin * 2;
  let y = margin;

  const addNewPageIfNeeded = (requiredSpace: number) => {
    if (y + requiredSpace > doc.internal.pageSize.getHeight() - margin) {
      doc.addPage();
      y = margin;
    }
  };

  // Header
  doc.setFillColor(13, 19, 33);
  doc.rect(0, 0, pageWidth, 40, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(18);
  doc.text("AlignX Listing Test Report", margin, 18);
  doc.setFontSize(9);
  doc.setTextColor(180, 180, 180);
  doc.text(`Generated: ${new Date().toLocaleString("zh-CN")}`, margin, 26);
  if (titleText) {
    doc.text(`Product: ${titleText.substring(0, 80)}${titleText.length > 80 ? "..." : ""}`, margin, 32);
  }
  y = 48;

  // Overall Score
  const scoreColor = result.overall_score >= 80 ? [34, 197, 94] : result.overall_score >= 60 ? [234, 179, 8] : [239, 68, 68];
  doc.setFillColor(240, 245, 255);
  doc.roundedRect(margin, y, contentWidth, 28, 3, 3, "F");
  doc.setFontSize(28);
  doc.setTextColor(scoreColor[0], scoreColor[1], scoreColor[2]);
  doc.text(String(result.overall_score), margin + 8, y + 18);
  doc.setFontSize(10);
  doc.setTextColor(60, 60, 60);
  doc.text("Overall Score", margin + 30, y + 10);
  doc.setFontSize(8);
  doc.setTextColor(100, 100, 100);
  const summaryLines = doc.splitTextToSize(result.overall_summary || "", contentWidth - 40);
  doc.text(summaryLines.slice(0, 2), margin + 30, y + 17);
  y += 34;

  // Quick scores bar
  const dims = [
    { label: "Title+Keywords", score: result.title_keywords.score },
    { label: "Main Image", score: result.main_image.score },
    { label: "A+ Description", score: result.a_plus_description.score },
    { label: "Bullet Points", score: result.bullet_points.score },
    { label: "Search Terms", score: result.backend_keywords.score },
  ];
  const barW = (contentWidth - 12) / 5;
  dims.forEach((d, i) => {
    const bx = margin + i * (barW + 3);
    doc.setFillColor(245, 247, 250);
    doc.roundedRect(bx, y, barW, 16, 2, 2, "F");
    doc.setFontSize(7);
    doc.setTextColor(100, 100, 100);
    doc.text(d.label, bx + 3, y + 6);
    const sc = d.score >= 80 ? [34, 197, 94] : d.score >= 60 ? [234, 179, 8] : [239, 68, 68];
    doc.setFontSize(12);
    doc.setTextColor(sc[0], sc[1], sc[2]);
    doc.text(String(d.score), bx + 3, y + 13);
  });
  y += 22;

  // Platform and intent alignment
  if (result.cosmo_alignment || result.rufus_alignment) {
    addNewPageIfNeeded(30);
    const halfW = (contentWidth - 4) / 2;
    if (result.cosmo_alignment) {
      doc.setFillColor(238, 242, 255);
      doc.roundedRect(margin, y, halfW, 24, 2, 2, "F");
      doc.setFontSize(8);
      doc.setTextColor(79, 70, 229);
      doc.text("Platform Alignment", margin + 3, y + 6);
      doc.setFontSize(7);
      doc.setTextColor(80, 80, 80);
      const cosmoLines = doc.splitTextToSize(result.cosmo_alignment, halfW - 6);
      doc.text(cosmoLines.slice(0, 3), margin + 3, y + 12);
    }
    if (result.rufus_alignment) {
      doc.setFillColor(245, 238, 255);
      doc.roundedRect(margin + halfW + 4, y, halfW, 24, 2, 2, "F");
      doc.setFontSize(8);
      doc.setTextColor(139, 92, 246);
      doc.text("Intent Match", margin + halfW + 7, y + 6);
      doc.setFontSize(7);
      doc.setTextColor(80, 80, 80);
      const rufusLines = doc.splitTextToSize(result.rufus_alignment, halfW - 6);
      doc.text(rufusLines.slice(0, 3), margin + halfW + 7, y + 12);
    }
    y += 30;
  }

  // Dimension details
  const dimDetails = [
    { label: "Title + Keywords", dim: result.title_keywords },
    { label: "Main Image", dim: result.main_image },
    { label: "A+ Description", dim: result.a_plus_description },
    { label: "Bullet Points", dim: result.bullet_points },
    { label: "Backend Search Terms", dim: result.backend_keywords },
  ];

  dimDetails.forEach((dd) => {
    const analysisLines = doc.splitTextToSize(dd.dim.analysis || "", contentWidth - 10);
    const sugLines = dd.dim.suggestions.map((s) => `• ${s}`);
    const totalSugLines = sugLines.flatMap((s) => doc.splitTextToSize(s, contentWidth - 14));
    const blockHeight = 14 + analysisLines.length * 3.5 + (totalSugLines.length > 0 ? 6 + totalSugLines.length * 3.5 : 0);

    addNewPageIfNeeded(blockHeight + 4);

    doc.setFillColor(248, 250, 252);
    doc.roundedRect(margin, y, contentWidth, blockHeight, 2, 2, "F");

    // Header
    doc.setFontSize(9);
    doc.setTextColor(30, 30, 30);
    doc.text(dd.label, margin + 4, y + 6);
    const sc2 = dd.dim.score >= 80 ? [34, 197, 94] : dd.dim.score >= 60 ? [234, 179, 8] : [239, 68, 68];
    doc.setTextColor(sc2[0], sc2[1], sc2[2]);
    doc.setFontSize(12);
    doc.text(String(dd.dim.score), margin + contentWidth - 16, y + 7);

    // Analysis
    doc.setFontSize(7);
    doc.setTextColor(80, 80, 80);
    let ay = y + 12;
    analysisLines.forEach((line: string) => {
      doc.text(line, margin + 4, ay);
      ay += 3.5;
    });

    // Suggestions
    if (totalSugLines.length > 0) {
      ay += 2;
      doc.setFontSize(7);
      doc.setTextColor(100, 100, 100);
      doc.text("Suggestions:", margin + 4, ay);
      ay += 4;
      totalSugLines.forEach((line: string) => {
        doc.text(line, margin + 6, ay);
        ay += 3.5;
      });
    }

    y += blockHeight + 4;
  });

  // Footer
  addNewPageIfNeeded(10);
  doc.setFontSize(7);
  doc.setTextColor(160, 160, 160);
  doc.text("Powered by AlignX Listing Optimization", margin, doc.internal.pageSize.getHeight() - 8);

  const filename = `AlignX_Report_${titleText ? titleText.substring(0, 20).replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, "_") : "listing"}_${new Date().toISOString().slice(0, 10)}.pdf`;
  doc.save(filename);
}

/* ------------------------------------------------------------------ */
/*  History Panel                                                      */
/* ------------------------------------------------------------------ */

function HistoryPanel({
  open,
  onClose,
  onLoadDetail,
}: {
  open: boolean;
  onClose: () => void;
  onLoadDetail: (detail: HistoryDetail) => void;
}) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [loadingId, setLoadingId] = useState<number | null>(null);

  const fetchHistory = useCallback(async (searchVal = "") => {
    setLoading(true);
    try {
      const data = await apiGetHistory(0, 50, searchVal);
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch {
      toast.error("加载历史记录失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) fetchHistory(search);
  }, [open, fetchHistory]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = () => fetchHistory(search);

  const handleLoad = async (id: number) => {
    setLoadingId(id);
    try {
      const detail = await apiGetDetail(id);
      onLoadDetail(detail);
      onClose();
      toast.success("已加载历史记录");
    } catch {
      toast.error("加载详情失败");
    } finally {
      setLoadingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiDeleteResult(id);
      setItems((prev) => prev.filter((it) => it.id !== id));
      setTotal((prev) => prev - 1);
      toast.success("已删除");
    } catch {
      toast.error("删除失败");
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "";
    try {
      return new Date(dateStr).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="relative ml-auto w-full max-w-md bg-gray-50 border-l border-gray-200 h-full flex flex-col animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-teal-600" />
            <h2 className="text-sm font-semibold text-gray-900">历史记录</h2>
            <span className="text-[10px] text-gray-500 bg-gray-50 px-1.5 py-0.5 rounded">{total}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} className="text-gray-500 hover:text-gray-900 h-7 w-7 p-0">
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Search */}
        <div className="p-3 border-b border-gray-100">
          <p className="mb-2 rounded-md border border-emerald-100 bg-emerald-50 px-2 py-1.5 text-[11px] text-emerald-700">
            查看历史只读取完整检测记录，不会重新生成评分。
          </p>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="搜索标题..."
                className="pl-8 h-8 text-xs bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600"
              />
            </div>
            <Button variant="outline" size="sm" onClick={handleSearch} className="h-8 text-xs border-gray-200 text-gray-600 hover:text-gray-900">
              搜索
            </Button>
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-teal-600" />
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500">
              <Clock className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">暂无历史记录</p>
            </div>
          ) : (
            items.map((item) => (
              <div
                key={item.id}
                className="bg-gray-50 border border-gray-200 rounded-lg p-3 hover:bg-white/[0.05] transition-colors group"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <p className="text-xs text-gray-900 font-medium line-clamp-2 flex-1">
                    {item.title || "未命名测试"}
                  </p>
                  <ScoreBadge score={item.overall_score} />
                </div>

                {/* Mini score bars */}
                <div className="grid grid-cols-4 gap-1.5 mb-2">
                  {[
                    { label: "标题", score: item.score_title_keywords },
                    { label: "主图", score: item.score_main_image },
                    { label: "A+", score: item.score_a_plus },
                    { label: "五点", score: item.score_bullet_points },
                  ].map((d) => (
                    <div key={d.label} className="text-center">
                      <div className="text-[9px] text-gray-500 mb-0.5">{d.label}</div>
                      <div className="w-full h-1 bg-gray-50 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${d.score >= 80 ? "bg-emerald-500" : d.score >= 60 ? "bg-amber-500" : "bg-red-500"}`}
                          style={{ width: `${d.score}%` }}
                        />
                      </div>
                      <div className={`text-[9px] mt-0.5 ${d.score >= 80 ? "text-emerald-600" : d.score >= 60 ? "text-amber-600" : "text-red-600"}`}>
                        {d.score}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-gray-600 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatDate(item.created_at)}
                    {item.has_images > 0 && (
                      <span className="ml-1 text-teal-600/60">
                        <ImageIcon className="w-3 h-3 inline" />
                      </span>
                    )}
                  </span>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleLoad(item.id)}
                      disabled={loadingId === item.id}
                      className="h-6 px-2 text-[10px] text-teal-600 hover:text-teal-300 hover:bg-teal-500/10"
                    >
                      {loadingId === item.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <ChevronLeft className="w-3 h-3 mr-0.5 rotate-180" />}
                      查看
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(item.id)}
                      className="h-6 px-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function PreLaunchTest() {
  const { loading: authLoading } = useRequireAuth();

  const [title, setTitle] = useState("");
  const [keywords, setKeywords] = useState("");
  const [category, setCategory] = useState("");
  const [price, setPrice] = useState("");
  const [targetPriceBand, setTargetPriceBand] = useState("");
  const [mainImages, setMainImages] = useState<string[]>([]);
  const [aPlusImages, setAPlusImages] = useState<string[]>([]);
  const [aPlusDesc, setAPlusDesc] = useState("");
  const [bulletPoints, setBulletPoints] = useState("");
  const [scoring, setScoring] = useState(false);
  const [result, setResult] = useState<ScoringResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [latestHistory, setLatestHistory] = useState<HistoryItem | null>(null);
  const [optimizationRound, setOptimizationRound] = useState(1);
  const [ocrStatus, setOcrStatus] = useState("");
  const [lastMainImageTexts, setLastMainImageTexts] = useState<string[]>([]);
  const [lastAPlusImageTexts, setLastAPlusImageTexts] = useState<string[]>([]);
  const inputFormRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    apiGetHistory(0, 1, "")
      .then((data) => setLatestHistory((data.items || [])[0] || null))
      .catch(() => setLatestHistory(null));
  }, []);

  const handleMainImagesAdd = useCallback(async (files: File[]) => {
    try {
      const base64List = await Promise.all(files.map(fileToBase64));
      setMainImages((prev) => [...prev, ...base64List].slice(0, MAX_MAIN_IMAGES));
      toast.success(`已添加 ${files.length} 张主图`);
    } catch {
      toast.error("部分图片读取失败，请重试");
    }
  }, []);

  const handleMainImageRemove = useCallback((index: number) => {
    setMainImages((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleMainImageReorder = useCallback((from: number, to: number) => {
    setMainImages((prev) => {
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  }, []);

  const handleAPlusImagesAdd = useCallback(async (files: File[]) => {
    try {
      const base64List = await Promise.all(files.map(fileToBase64));
      setAPlusImages((prev) => [...prev, ...base64List].slice(0, MAX_APLUS_IMAGES));
      toast.success(`已添加 ${files.length} 张A+图片`);
    } catch {
      toast.error("部分图片读取失败，请重试");
    }
  }, []);

  const handleAPlusImageRemove = useCallback((index: number) => {
    setAPlusImages((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const appendUniqueLines = (current: string, additions: string[]) => {
    const lines = current.split(/\n+/).map((line) => line.trim()).filter(Boolean);
    const seen = new Set(lines.map((line) => line.toLowerCase()));
    additions.forEach((line) => {
      const clean = line.trim();
      if (clean && !seen.has(clean.toLowerCase())) {
        lines.push(clean);
        seen.add(clean.toLowerCase());
      }
    });
    return lines.join("\n");
  };

  const appendUniqueCsv = (current: string, additions: string[]) => {
    const items = current.split(/[,，\n]+/).map((item) => item.trim()).filter(Boolean);
    const seen = new Set(items.map((item) => item.toLowerCase()));
    additions.forEach((item) => {
      const clean = item.trim();
      if (clean && !seen.has(clean.toLowerCase())) {
        items.push(clean);
        seen.add(clean.toLowerCase());
      }
    });
    return items.join(", ");
  };

  const productHint = `${title} ${category}`.toLowerCase();
  const getProductProfile = () => {
    if (/cat|litter|odor|deodorizer|pet|air purifier|臭|猫砂|除味|宠物/.test(productHint)) {
      return {
        defaultTitle: "Cat Litter Odor Deodorizer for Pet Home and Small Room with Quiet Odor Control",
        titlePatch: "for Cat Litter Room and Pet Home with Quiet Odor Control",
        keywords: [
          "cat litter odor deodorizer",
          "pet room odor control",
          "odor remover for litter box",
          "quiet air freshener for pets",
          "cat room smell control",
          "small room deodorizer for apartment",
          "pet home odor eliminator",
          "litter box smell reducer",
          "safe odor control for cats",
          "bathroom kitchen pet odor remover",
        ],
        bullets: [
          "Function: targets cat litter odor and everyday pet room smells with a compact deodorizing design.",
          "Effect: helps reduce lingering ammonia and bathroom odors so the room feels cleaner between litter changes.",
          "Scenario: made for cat rooms apartments bathrooms kitchens and small pet living spaces.",
          "Trust: quiet ozone free operation supports daily use around home areas where pets and people stay.",
          "Support: simple setup and easy maintenance help buyers use it consistently after delivery.",
        ],
        aplus: [
          "1 Brand Promise: Built for homes where cat litter odor is a real daily problem and buyers need a cleaner small room experience without complicated setup.",
          "2 Technology Principle: The deodorizing structure is positioned as a targeted odor control aid for pet spaces and should explain how air contact and placement help reduce smell around the litter area.",
          "3 Scenario Education: Show a cat room apartment bathroom kitchen and bedroom corner so shoppers immediately understand where the product should be placed and when it is useful.",
          "4 Benefit Proof: Use before and after room odor language carefully and focus on reduced lingering smell cleaner air feeling and easier daily pet care.",
          "5 Differentiation: Compare with sprays candles and bulky purifiers by emphasizing compact placement quiet use and no need to cover odor with fragrance.",
          "6 Size and Compatibility: Show product dimensions cord length placement distance and suitable room types so buyers can judge fit before purchase.",
          "7 Safety and Trust: Explain ozone free use material safety and quiet operation in plain evidence based language without absolute medical or guaranteed claims.",
          "8 Use and Maintenance: Show plug in placement cleaning reminders and recommended use habits to reduce wrong expectations.",
          "9 After Sale Loop: Close with setup help maintenance guidance and responsive support so buyers feel risk is controlled after delivery.",
        ].join("\n"),
      };
    }
    if (/case|iphone|magsafe|phone|手机壳|保护壳/.test(productHint)) {
      return {
        defaultTitle: "Magnetic Phone Case for iPhone with MagSafe Compatibility and Drop Protection",
        titlePatch: "for iPhone with MagSafe Compatibility and Drop Protection",
        keywords: [
          "clear magnetic case for iphone",
          "magsafe compatible phone case",
          "anti yellowing phone case",
          "military grade drop protection case",
          "slim protective iphone cover",
          "clear case with screen protector",
          "shockproof phone bumper case",
          "wireless charging compatible case",
          "camera protection iphone case",
          "everyday protective phone case",
        ],
        bullets: [
          "Function: magnetic ring supports MagSafe style charging and daily accessory alignment.",
          "Effect: raised edges and reinforced corners help reduce drop impact and camera scratches.",
          "Scenario: clear slim profile works for commuting travel office and everyday phone carry.",
          "Trust: anti yellowing material and fitted buttons help keep the case usable over time.",
          "Support: easy installation and responsive replacement support reduce purchase risk.",
        ],
        aplus: [
          "1 Brand Promise: Protect the phone without hiding the original look and make daily charging easier.",
          "2 Technology Principle: Explain the magnetic alignment structure corner buffer design raised camera edge and screen lip in simple visual proof.",
          "3 Scenario Education: Show commuting office travel pocket use and one hand grip so shoppers know this is an everyday protective case.",
          "4 Benefit Proof: Demonstrate drop protection scratch reduction button response wireless charging and clear back visibility.",
          "5 Differentiation: Compare ordinary clear cases loose magnetic cases and bulky rugged cases by showing magnetic strength fit and slim protection.",
          "6 Size and Compatibility: State exact iPhone model compatibility and show port camera button and charging alignment.",
          "7 Safety and Trust: Use material and durability proof without unverifiable absolute claims.",
          "8 Use and Maintenance: Show installation cleaning anti yellowing care and charging notes.",
          "9 After Sale Loop: Offer fit support and replacement guidance if model selection or installation is wrong.",
        ].join("\n"),
      };
    }
    if (/power bank|charger|battery|充电|移动电源/.test(productHint)) {
      return {
        defaultTitle: "Portable Power Bank for Travel and Everyday Backup Charging with USB C",
        titlePatch: "for Travel and Everyday Backup Charging with USB C",
        keywords: [
          "travel power bank",
          "compact charger for small purse",
          "usb c power bank for iphone",
          "portable phone charger for samsung",
          "slim pocket power bank",
          "lightweight charger for flights",
          "backup battery for commute",
          "fast charging portable charger",
          "power bank with cable",
          "emergency phone battery pack",
        ],
        bullets: [
          "Function: portable backup battery helps keep phones charged during travel commute and daily use.",
          "Effect: USB C charging support reduces low battery risk when outlets are not available.",
          "Scenario: slim size fits small bags pockets flights office days and weekend trips.",
          "Trust: clear capacity input output and device compatibility details help buyers choose correctly.",
          "Support: simple charging steps and after sale help reduce setup and compatibility concerns.",
        ],
        aplus: [
          "1 Brand Promise: Give buyers a reliable daily backup charging option for travel and busy days.",
          "2 Technology Principle: Explain capacity input output USB C interface cable use and device compatibility clearly.",
          "3 Scenario Education: Show airport commute office school outdoor and emergency battery situations.",
          "4 Benefit Proof: Explain how it helps avoid low battery anxiety and keeps phones available for calls maps and payments.",
          "5 Differentiation: Compare bulky chargers wall chargers and low capacity backups by size portability and practical output.",
          "6 Size and Compatibility: Show dimensions weight supported phones and charging cable requirements.",
          "7 Safety and Trust: Describe protection features and material evidence without absolute safety claims.",
          "8 Use and Maintenance: Show first charge recharge indicators storage and travel notes.",
          "9 After Sale Loop: Provide compatibility help and replacement support for defective charging issues.",
        ].join("\n"),
      };
    }
    if (/speaker|bluetooth|音箱|扬声器/.test(productHint)) {
      return {
        defaultTitle: "Waterproof Bluetooth Speaker for Camping Pool Beach and Travel",
        titlePatch: "for Camping Pool Beach and Travel with Waterproof Portable Sound",
        keywords: [
          "waterproof bluetooth speaker",
          "portable speaker for camping",
          "poolside bluetooth speaker",
          "speaker for hiking and travel",
          "bluetooth speaker with fm radio",
          "outdoor wireless speaker",
          "compact speaker for beach",
          "portable party speaker",
          "speaker for shower and patio",
          "travel bluetooth speaker",
        ],
        bullets: [
          "Function: portable Bluetooth speaker delivers wireless sound for music calls and outdoor use.",
          "Effect: water resistant design helps reduce worry around splashes poolside use and beach trips.",
          "Scenario: built for camping hiking patio shower travel and small gatherings.",
          "Trust: clear battery connection and waterproof level details help buyers set the right expectation.",
          "Support: simple pairing and responsive support reduce setup problems after delivery.",
        ],
        aplus: [
          "1 Brand Promise: Make outdoor and travel music easier without a bulky audio setup.",
          "2 Technology Principle: Explain Bluetooth pairing sound driver battery waterproof level and control layout.",
          "3 Scenario Education: Show camping pool beach shower patio and travel bag use cases.",
          "4 Benefit Proof: Demonstrate portable sound splash resistance battery life and easy pairing.",
          "5 Differentiation: Compare phone speakers large speakers and non waterproof speakers by portability and scene fit.",
          "6 Size and Compatibility: Show dimensions weight device compatibility and charging interface.",
          "7 Safety and Trust: Explain waterproof limits and charging precautions in clear evidence based language.",
          "8 Use and Maintenance: Show pairing steps cleaning drying and storage recommendations.",
          "9 After Sale Loop: Provide pairing help battery support and replacement guidance if needed.",
        ].join("\n"),
      };
    }
    return {
      defaultTitle: "Product for Everyday Use with Clear Benefits and Low Risk Setup",
      titlePatch: "for Everyday Use with Clear Benefits and Low Risk Setup",
      keywords: [
        "everyday use product",
        "easy setup product",
        "compact home use item",
        "gift ready useful product",
        "low risk purchase",
        "practical product for home",
        "portable daily use item",
        "simple maintenance product",
        "problem solving product",
        "trusted everyday accessory",
      ],
      bullets: [
        "Function: explains the core job clearly so shoppers understand what the product does.",
        "Effect: connects the feature to a practical result and reduces uncertainty before purchase.",
        "Scenario: shows who uses it where it is used and why that moment matters.",
        "Trust: includes material fit safety compatibility or evidence details buyers can verify.",
        "Support: explains setup maintenance and after sale help to reduce post purchase risk.",
      ],
      aplus: [
        "1 Brand Promise: Explain the user problem and the product role in one clear scenario.",
        "2 Technology Principle: Show the core structure material or mechanism that creates the benefit.",
        "3 Scenario Education: Use real scenes to help shoppers recognize when they need the product.",
        "4 Benefit Proof: Connect every feature to a practical result that can be seen or verified.",
        "5 Differentiation: Compare against common alternatives and explain why this option is easier safer or more practical.",
        "6 Size and Compatibility: Clarify dimensions fit package contents and limitations.",
        "7 Safety and Trust: Add material certification warranty or careful use evidence without exaggerated claims.",
        "8 Use and Maintenance: Show setup steps care instructions and mistake prevention.",
        "9 After Sale Loop: Close with support replacement and service expectations so buyers feel protected.",
      ].join("\n"),
    };
  };

  const productProfile = getProductProfile();
  const suggestedKeywords = productProfile.keywords;

  const buildOptimizedTitle = () => {
    const current = title.trim();
    if (!current) return productProfile.defaultTitle;
    const lower = current.toLowerCase();
    const hasRelation = /\b(for|with|without|compatible|fits)\b/.test(lower);
    const hasState = /\b(odor|control|safe|quiet|waterproof|portable|charging|protection|easy|compact|reduce|anti|drop)\b/.test(lower);
    if (hasRelation && hasState) return current;
    const patched = `${current} ${productProfile.titlePatch}`;
    return patched.length > 190 ? patched.slice(0, 187).trim() : patched;
  };

  const replaceWithOptimizedInput = () => {
    setSaved(false);
    setResult(null);
    setOptimizationRound((prev) => prev + 1);
    inputFormRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const applyDimensionFix = (dimension: PrelaunchDimensionKey, dim: DimensionScore) => {
    const suggestions = dim.suggestions.filter(Boolean);
    const recommendedText = (dim.recommended_text || "").trim();
    const recommendedKeywords = (dim.validation_keywords || []).filter(Boolean);
    if (dimension === "title_keywords") {
      setTitle(recommendedText || buildOptimizedTitle());
      setKeywords(appendUniqueCsv("", recommendedKeywords.length ? recommendedKeywords : suggestedKeywords));
    }
    if (dimension === "backend_keywords") {
      setKeywords(recommendedText || appendUniqueCsv("", recommendedKeywords.length ? recommendedKeywords : suggestedKeywords));
    }
    if (dimension === "main_image") {
      if (mainImages.length < MAX_MAIN_IMAGES) {
        inputFormRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        toast.warning("主图/副图维度需要补齐7张图片并按职责排序，文本回填不能代替图片证据");
        return;
      }
      setAPlusDesc((prev) => appendUniqueLines(prev, [
        recommendedText || "Image brief: 1 white background click image 2 core benefit proof 3 real use scenario 4 size and structure 5 competitor comparison 6 safety or material proof 7 package setup and use steps.",
      ]));
    }
    if (dimension === "a_plus_description") {
      setAPlusDesc(appendUniqueLines(recommendedText || productProfile.aplus, suggestions.slice(0, 2).map((item) => `Extra review note: ${item}`)));
      if (aPlusImages.length < MAX_APLUS_IMAGES) {
        toast.warning("已回填A+文本闭环；A+要稳定到80分以上，还需要补齐9张A+图并按顺序上传");
      }
    }
    if (dimension === "bullet_points") {
      setBulletPoints(recommendedText || productProfile.bullets.join("\n"));
    }
    replaceWithOptimizedInput();
    toast.success("已把优化建议回填到输入区，请重新检测分数");
  };

  const runImageOcr = async (images: string[], label: string) => {
    if (images.length === 0) return [];
    try {
      const { createWorker, OEM, PSM } = await import("tesseract.js");
      setOcrStatus(`正在识别${label}图片文案 0/${images.length}`);
      const worker = await createWorker("eng", OEM.LSTM_ONLY, {
        logger: (message: { status?: string; progress?: number }) => {
          if (message.status === "recognizing text") {
            const progress = Math.round((message.progress || 0) * 100);
            setOcrStatus(`正在识别${label}图片文案 ${progress}%`);
          }
        },
      }, {
        tessedit_pageseg_mode: PSM.AUTO,
      });
      const texts: string[] = [];
      for (let index = 0; index < images.length; index += 1) {
        setOcrStatus(`正在识别${label}第 ${index + 1}/${images.length} 张图片文案`);
        const { data } = await worker.recognize(images[index]);
        texts.push((data.text || "").replace(/\s+/g, " ").trim());
      }
      await worker.terminate();
      setOcrStatus("");
      return texts;
    } catch {
      setOcrStatus("");
      toast.warning(`${label}图片识别暂不可用，已继续按图片数量和文本描述评分`);
      return [];
    }
  };

  const runScoring = async () => {
    if (!title.trim() && !bulletPoints.trim()) {
      toast.error("请至少输入标题或五点描述");
      return;
    }

    const moduleTaskId = `listing-launch-check:${Date.now()}`;
    setScoring(true);
    setResult(null);
    setSaved(false);
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "listing-launch-check",
      label: "上新检测评分",
      status: "running",
      detail: "正在识别图片并生成上架前诊断",
      path: "/listing-launch-check",
    });
    try {
      const mainImageTexts = await runImageOcr(mainImages, "主图/辅图");
      const aPlusImageTexts = await runImageOcr(aPlusImages, "A+");
      setLastMainImageTexts(mainImageTexts);
      setLastAPlusImageTexts(aPlusImageTexts);
      const parsed = await apiEvaluateLaunch({
        title,
        keywords,
        bullet_points: bulletPoints,
        a_plus_desc: aPlusDesc,
        category,
        price,
        target_price_band: targetPriceBand,
        main_image_count: mainImages.length,
        a_plus_image_count: aPlusImages.length,
        main_image_texts: mainImageTexts,
        a_plus_image_texts: aPlusImageTexts,
        use_ai: true,
      });
      setResult(parsed);
      finishModuleTask(moduleTaskId, "completed", "上新检测完成");
      toast.success(parsed.ai_called ? "上新检测完成，已生成图片与文案建议" : "上新检测完成，已生成系统评分");
      saveScoringResult(parsed, true, { mainImageTexts, aPlusImageTexts }).catch(() => {});
    } catch (err) {
      const msg = err instanceof Error ? err.message : "评分失败，请稍后重试";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
    } finally {
      setScoring(false);
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  };

  const saveScoringResult = async (
    targetResult: ScoringResult,
    silent = false,
    ocrOverride?: { mainImageTexts: string[]; aPlusImageTexts: string[] }
  ) => {
    if (!targetResult) return false;
    if (!silent) setSaving(true);
    try {
      const hasMainImgs = mainImages.length > 0;
      const hasAPlusImgs = aPlusImages.length > 0;
      let hasImages = 0;
      if (hasMainImgs && hasAPlusImgs) hasImages = 3;
      else if (hasAPlusImgs) hasImages = 2;
      else if (hasMainImgs) hasImages = 1;

      const payload = {
        title: title || "未命名测试",
        keywords,
        bullet_points: bulletPoints,
        a_plus_desc: aPlusDesc,
        input_snapshot: {
          title,
          keywords,
          bullet_points: bulletPoints,
          a_plus_desc: aPlusDesc,
          category,
          price,
          target_price_band: targetPriceBand,
          main_image_count: mainImages.length,
          a_plus_image_count: aPlusImages.length,
          main_image_ocr_texts: ocrOverride?.mainImageTexts || lastMainImageTexts,
          a_plus_image_ocr_texts: ocrOverride?.aPlusImageTexts || lastAPlusImageTexts,
          optimization_round: optimizationRound,
        },
        saved_kind: "full_prelaunch_record",
        optimization_round: optimizationRound,
        overall_score: targetResult.overall_score,
        title_keywords: targetResult.title_keywords,
        main_image: targetResult.main_image,
        a_plus_description: targetResult.a_plus_description,
        bullet_points_score: targetResult.bullet_points,
        backend_keywords: targetResult.backend_keywords,
        overall_summary: targetResult.overall_summary,
        cosmo_alignment: targetResult.cosmo_alignment,
        rufus_alignment: targetResult.rufus_alignment,
        ordered_first_fixes: targetResult.ordered_first_fixes || [],
        rule_context: targetResult.rule_context || {},
        vision_alignment: targetResult.vision_alignment || {},
        product_attribute_profile: targetResult.product_attribute_profile || {},
        prelaunch_modification_plan: targetResult.prelaunch_modification_plan || {},
        ad_validation_alignment: targetResult.ad_validation_alignment || {},
        ad_validation_plan: targetResult.ad_validation_plan || {},
        has_images: hasImages,
      };

      const res = await apiSaveResult(payload);
      if (res.success) {
        setSaved(true);
        apiGetHistory(0, 1, "").then((data) => setLatestHistory((data.items || [])[0] || null)).catch(() => {});
        saveActionSnapshot({
          module_key: "prelaunch_test",
          module_name: "上新检测",
          action_key: "run_prelaunch_check",
          action_name: "Listing上新检测",
          asin: "",
          title: title || "未命名测试",
          input_snapshot: {
            title,
            keywords,
            bullet_points: bulletPoints,
            a_plus_desc: aPlusDesc,
            category,
            price,
            target_price_band: targetPriceBand,
          image_count: mainImages.length + aPlusImages.length,
          main_image_ocr_texts: ocrOverride?.mainImageTexts || lastMainImageTexts,
          a_plus_image_ocr_texts: ocrOverride?.aPlusImageTexts || lastAPlusImageTexts,
          optimization_round: optimizationRound,
          },
          output_snapshot: targetResult,
          data_source: "full_prelaunch_record",
          confidence: targetResult.overall_score >= 80 ? "high" : targetResult.overall_score >= 60 ? "medium" : "low",
          ai_called: Boolean((targetResult as { ai_called?: boolean }).ai_called),
          source_record_table: "prelaunch_test_results",
          source_record_id: res.id || null,
        }).catch(() => {});
        if (!silent) toast.success("评分结果已保存");
        return true;
      } else {
        if (!silent) toast.error(res.message || "保存失败");
        return false;
      }
    } catch {
      if (!silent) toast.error("保存失败，请重试");
      return false;
    } finally {
      if (!silent) setSaving(false);
    }
  };

  /* Save result to backend */
  const handleSave = async () => {
    if (!result) return;
    await saveScoringResult(result, false);
  };

  /* Export PDF */
  const handleExportPDF = () => {
    if (!result) return;
    try {
      generatePDF(result, title);
      toast.success("PDF 已导出");
    } catch {
      toast.error("PDF 导出失败");
    }
  };

  /* Load history detail */
  const handleLoadDetail = (detail: HistoryDetail) => {
    setTitle(detail.title || "");
    setKeywords(detail.keywords || "");
    setBulletPoints(detail.bullet_points || "");
    setAPlusDesc(detail.a_plus_desc || "");
    setMainImages([]);
    setAPlusImages([]);

    // Reconstruct result from full_report
    const report = detail.full_report || {};
    const parseDim = (d: Record<string, unknown> | undefined): DimensionScore => ({
      score: (d?.score as number) || 0,
      analysis: (d?.analysis as string) || "",
      suggestions: (d?.suggestions as string[]) || [],
      recommended_text: (d?.recommended_text as string) || "",
      validation_hypothesis: (d?.validation_hypothesis as string) || "",
      attribution_metric: (d?.attribution_metric as string) || "",
      validation_keywords: (d?.validation_keywords as string[]) || [],
      failed_scale: (d?.failed_scale as string[]) || [],
      current_gap: (d?.current_gap as string) || "",
      recommended_change: (d?.recommended_change as string) || "",
    });

    const reconstructed: ScoringResult = {
      title_keywords: parseDim(report.title_keywords as Record<string, unknown>),
      main_image: parseDim(report.main_image as Record<string, unknown>),
      a_plus_description: parseDim(report.a_plus_description as Record<string, unknown>),
      bullet_points: parseDim(report.bullet_points as Record<string, unknown>),
      backend_keywords: parseDim(report.backend_keywords as Record<string, unknown>),
      overall_score: (report.overall_score as number) || detail.overall_score || 0,
      overall_summary: (report.overall_summary as string) || detail.overall_summary || "",
      cosmo_alignment: (report.cosmo_alignment as string) || detail.cosmo_alignment || "",
      rufus_alignment: (report.rufus_alignment as string) || detail.rufus_alignment || "",
      ordered_first_fixes: (report.ordered_first_fixes as string[]) || [],
      rule_context: (report.rule_context as Record<string, unknown>) || {},
      vision_alignment: (report.vision_alignment as Record<string, unknown>) || {},
      product_attribute_profile: (report.product_attribute_profile as Record<string, unknown>) || {},
      prelaunch_modification_plan: (report.prelaunch_modification_plan as Record<string, unknown>) || {},
      ad_validation_alignment: (report.ad_validation_alignment as Record<string, unknown>) || {},
      ad_validation_plan: (report.ad_validation_plan as Record<string, unknown>) || {},
    };

    setResult(reconstructed);
    setSaved(true); // Already saved
  };

  const loadLatestHistory = async () => {
    if (!latestHistory) return;
    try {
      const detail = await apiGetDetail(latestHistory.id);
      handleLoadDetail(detail);
      toast.success("已加载最近一次上新检测");
    } catch {
      toast.error("加载上新检测失败");
    }
  };

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <Loader2 className="w-8 h-8 animate-spin text-brand-600" />
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#f5f5f7] text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto bg-[#f5f5f7]">
        <div className="p-4 sm:p-6 max-w-5xl mx-auto pt-14 md:pt-6">
          {/* Header */}
          <div className="mb-6 flex items-start justify-between">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
                <ClipboardCheck className="w-5 h-5 sm:w-6 sm:h-6 text-teal-600" />
                Listing 上新检测
              </h1>
              <p className="text-gray-500 mt-1 text-sm">
                上架前判断 Listing 是否具备上线条件，识别必改项、缺词和表达错配
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setHistoryOpen(true)}
              className="border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-100 gap-1.5 shrink-0"
            >
              <History className="w-3.5 h-3.5" />
              历史记录
            </Button>
          </div>

          <PageHeader
            objective="上架前判断Listing是否建议上架"
            inputSource="标题、五点、主图/副图、A+、后台搜索关键词"
            process="按评论需求、平台识别和转化承接做上新准入检测"
            outputTarget="是否建议上架、风险等级、必改项、缺失关键词、表达错配点"
            action="修改必改项后进入本品诊断，生成广告验证假设"
            feedback="每一轮检测完整保存为历史记录，作为本品诊断和后续广告验证基线"
            tone="teal"
          />

          {latestHistory && !result && (
            <Card className="bg-teal-50 border-teal-100 p-4 mb-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold text-teal-700 mb-1">最近上新检测</p>
                  <h2 className="text-sm font-semibold text-gray-900 line-clamp-1">{latestHistory.title}</h2>
                  <p className="text-xs text-gray-600 mt-1">
                    上新准入分 {latestHistory.overall_score} · 标题 {latestHistory.score_title_keywords} · 主图 {latestHistory.score_main_image} · 五点 {latestHistory.score_bullet_points}
                  </p>
                </div>
                <Button
                  size="sm"
                  onClick={loadLatestHistory}
                  className="bg-teal-600 hover:bg-teal-500 text-white shrink-0"
                >
                  <CheckCircle2 className="w-4 h-4 mr-1.5" />
                  加载演示检测
                </Button>
              </div>
            </Card>
          )}

          {/* Input Form */}
          <Card ref={inputFormRef} className="bg-white border-gray-200 p-4 sm:p-5 mb-6 space-y-4">
            <div>
              <label className="text-sm text-gray-500 mb-1.5 block flex items-center gap-1.5">
                <Type className="w-3.5 h-3.5" /> 产品标题 *
              </label>
              <Textarea
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="输入完整的Amazon产品标题..."
                className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600 min-h-[88px] resize-y leading-6"
              />
            </div>

            <div>
              <label className="text-sm text-gray-500 mb-1.5 block flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5" /> 搜索关键词
              </label>
              <Textarea
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="输入后台搜索关键词，逗号分隔..."
                className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600 min-h-[76px] resize-y leading-6"
              />
            </div>

            <div>
              <label className="text-sm text-gray-500 mb-1.5 block flex items-center gap-1.5">
                <List className="w-3.5 h-3.5" /> 五点描述 *
              </label>
              <Textarea
                value={bulletPoints}
                onChange={(e) => setBulletPoints(e.target.value)}
                placeholder="输入五点描述，每条一行：&#10;• 第一点描述...&#10;• 第二点描述...&#10;• 第三点描述...&#10;• 第四点描述...&#10;• 第五点描述..."
                className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600 min-h-[240px] resize-y leading-6"
              />
              <p className="mt-1.5 text-[11px] text-gray-500">
                五点每点只讲一个购买理由：功能、效果、场景、信任、售后；避免空喊 high quality / best / premium。
              </p>
            </div>

            <div>
              <label className="text-sm text-gray-500 mb-1.5 block flex items-center gap-1.5">
                <ImageIcon className="w-3.5 h-3.5" /> 产品主图（最多7张，可拖拽排序）
              </label>
              <p className="mb-2 text-[11px] text-gray-500">
                7张图职责：1主图点击，2核心卖点，3使用场景，4尺寸/结构，5竞品对比，6安全/材质认证，7包装/安装/使用步骤。
              </p>
              <MainImageUploadZone
                images={mainImages}
                onAdd={handleMainImagesAdd}
                onRemove={handleMainImageRemove}
                onReorder={handleMainImageReorder}
              />
            </div>

            <div>
              <label className="text-sm text-gray-500 mb-1.5 block flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" /> A+图文描述
              </label>
              <Textarea
                value={aPlusDesc}
                onChange={(e) => setAPlusDesc(e.target.value)}
                placeholder="描述A+内容：品牌故事、对比图、场景图、尺寸图..."
                className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600 min-h-[120px] resize-y leading-6"
              />
              <div className="mt-2">
                <p className="text-[10px] text-gray-500 mb-1.5">
                  上传A+图片（最多9张），将按A+素材矩阵、图文承接和图片文案规范评分
                </p>
                <p className="mb-2 text-[11px] text-gray-500">
                  A+ 9张顺序：1品牌承诺，2技术原理，3场景教育，4利益证明，5差异化对比，6尺寸/适配，7安全认证，8使用维护，9售后保障。
                </p>
                <APlusImageUploadZone
                  images={aPlusImages}
                  onAdd={handleAPlusImagesAdd}
                  onRemove={handleAPlusImageRemove}
                />
              </div>
            </div>

            <Button
              onClick={runScoring}
              disabled={scoring}
              className="w-full sm:w-auto bg-gradient-to-r from-teal-600 to-teal-600 hover:from-teal-500 hover:to-teal-500 text-gray-900 shadow-lg shadow-teal-500/20 h-10"
            >
              {scoring ? (
                <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> 检测中...</>
              ) : (
                <><Sparkles className="w-4 h-4 mr-1.5" /> {(mainImages.length > 0 || aPlusImages.length > 0) ? "开始上新检测（含图片）" : "开始上新检测"}</>
              )}
            </Button>
          </Card>

          {/* Loading */}
          {scoring && (
            <Card className="bg-white border-gray-200 p-6 mb-6">
              <div className="flex flex-col items-center justify-center py-8">
                <Loader2 className="w-10 h-10 animate-spin text-teal-600 mb-4" />
                <p className="text-sm font-medium text-gray-600 mb-2">
                  {ocrStatus || "正在进行上新准入检测"}
                </p>
                <p className="text-xs text-gray-500 text-center max-w-sm">
                  正在识别图片文案，并按评论需求、平台识别、转化承接、图片顺序和素材完整度评分。
                </p>
              </div>
            </Card>
          )}

          {/* Results */}
          {result && (
            <div className="space-y-6">
              {(() => {
                const readiness = buildLaunchReadiness(result, keywords);
                const riskClass = readiness.riskLevel === "低"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : readiness.riskLevel === "中"
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : "bg-red-50 text-red-700 border-red-200";
                return (
                  <Card className="bg-white border-gray-200 p-5">
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-4">
                      <div>
                        <h2 className="text-lg font-bold text-gray-900">上新准入结论</h2>
                        <p className="text-xs text-gray-500 mt-1">先把本品Listing承接校准，再进入广告验证，减少试错成本与时间成本。</p>
                      </div>
                      <div className="flex gap-2">
                        <span className={`px-3 py-1.5 rounded-lg border text-sm font-semibold ${riskClass}`}>
                          {readiness.launchAdvice}
                        </span>
                        <span className={`px-3 py-1.5 rounded-lg border text-sm font-semibold ${riskClass}`}>
                          风险{readiness.riskLevel}
                        </span>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {[
                        { label: "必改项", items: readiness.mustFix },
                        { label: "缺失关键词", items: readiness.missingKeywords },
                        { label: "表达错配点", items: readiness.mismatchPoints },
                        { label: "上新前修改建议", items: readiness.preLaunchActions.length ? readiness.preLaunchActions : ["当前建议保留现有结构，补充竞品和广告验证基线"] },
                      ].map((block) => (
                        <div key={block.label} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                          <p className="text-[11px] font-semibold text-gray-500 mb-2">{block.label}</p>
                          <ul className="space-y-1">
                            {block.items.map((item, index) => (
                              <li key={index} className="text-xs text-gray-700 leading-relaxed flex gap-1.5">
                                <span className="text-teal-600 mt-0.5">•</span>
                                <span>{item}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </Card>
                );
              })()}

              {result.ordered_first_fixes && result.ordered_first_fixes.length > 0 && (
                <Card className="bg-brand-50 border-brand-100 p-5">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-brand-600">
                      <TrendingUp className="h-4 w-4" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-sm font-semibold text-brand-800">建议修改顺序</h3>
                      <p className="mt-1 text-xs text-brand-700/80">
                        系统按模块职责判断先后：标题归类 → 主图点击 → 辅图转化 → 五点购买理由 → Search Terms补充匹配 → A+信任闭环。
                      </p>
                      <div className="mt-3 space-y-2">
                        {result.ordered_first_fixes.map((item, index) => (
                          <div key={`${item}-${index}`} className="flex gap-2 rounded-lg border border-brand-100 bg-white px-3 py-2 text-xs text-gray-700">
                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-600 text-[10px] font-bold text-white">
                              {index + 1}
                            </span>
                            <span>{item}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </Card>
              )}

              {/* Action Bar */}
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSave}
                  disabled={saving || saved}
                  className={`border-gray-200 gap-1.5 ${saved ? "text-emerald-600 border-emerald-200 bg-emerald-500/5" : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"}`}
                >
                  {saving ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : saved ? (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  ) : (
                    <Save className="w-3.5 h-3.5" />
                  )}
                  {saved ? "完整记录已保存" : "保存完整记录"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleExportPDF}
                  className="border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-100 gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  导出 PDF
                </Button>
              </div>

              {/* Overall Score */}
              <Card className="bg-white border-gray-200 p-5">
                <div className="flex items-center gap-4 mb-4">
                  <ScoreRing score={result.overall_score} size={80} />
                  <div>
                    <h2 className="text-lg font-bold text-gray-900">上新检测评分</h2>
                    <p className="text-xs text-gray-500 mt-1 leading-relaxed max-w-xl">{result.overall_summary}</p>
                  </div>
                </div>

                {/* Quick score bars */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-4">
                  {[
                    { label: "标题+关键词", score: result.title_keywords.score },
                    { label: "主图", score: result.main_image.score },
                    { label: "A+图文", score: result.a_plus_description.score },
                    { label: "五点描述", score: result.bullet_points.score },
                    { label: "后台关键词", score: result.backend_keywords.score },
                  ].map((item) => (
                    <div key={item.label} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs text-gray-500">{item.label}</span>
                        <span className={`text-sm font-bold ${item.score >= 80 ? "text-emerald-600" : item.score >= 60 ? "text-amber-600" : "text-red-600"}`}>
                          {item.score}
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-gray-50 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${item.score >= 80 ? "bg-emerald-500" : item.score >= 60 ? "bg-amber-500" : "bg-red-500"}`}
                          style={{ width: `${item.score}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Platform and intent alignment */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {result.cosmo_alignment && (
                  <Card className="bg-white border-gray-200 p-4">
                    <h3 className="text-sm font-semibold text-brand-600 mb-2 flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5" /> 平台识别对齐度
                    </h3>
                    <p className="text-xs text-gray-500 leading-relaxed">{result.cosmo_alignment}</p>
                  </Card>
                )}
                {result.rufus_alignment && (
                  <Card className="bg-white border-gray-200 p-4">
                    <h3 className="text-sm font-semibold text-gold-400 mb-2 flex items-center gap-1.5">
                      <TrendingUp className="w-3.5 h-3.5" /> 用户意图匹配度
                    </h3>
                    <p className="text-xs text-gray-500 leading-relaxed">{result.rufus_alignment}</p>
                  </Card>
                )}
              </div>

              {/* 4 Dimension Scores */}
              <Card className="bg-brand-50 border-brand-100 p-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-brand-700">上新前迭代</p>
                    <p className="text-xs text-brand-600/80 mt-1">
                      低于80分的维度可以点击“按推荐回填”，系统会按产品属性回填可执行修改，再重新检测；每一轮都会完整保存。
                    </p>
                  </div>
                  <Badge variant="outline" className="border-brand-200 bg-white text-brand-700">
                    第 {optimizationRound} 轮
                  </Badge>
                </div>
              </Card>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <DimScoreCard
                  title="标题 + 关键词"
                  icon={<Type className="w-4 h-4 text-teal-600" />}
                  dim={result.title_keywords}
                  color="bg-teal-50"
                  dimensionKey="title_keywords"
                  onApplyFix={applyDimensionFix}
                />
                <DimScoreCard
                  title="主图/副图承接"
                  icon={<ImageIcon className="w-4 h-4 text-emerald-600" />}
                  dim={result.main_image}
                  color="bg-emerald-50"
                  dimensionKey="main_image"
                  onApplyFix={applyDimensionFix}
                />
                <DimScoreCard
                  title="A+ 图文描述"
                  icon={<FileText className="w-4 h-4 text-gold-600" />}
                  dim={result.a_plus_description}
                  color="bg-gold-50"
                  dimensionKey="a_plus_description"
                  onApplyFix={applyDimensionFix}
                />
                <DimScoreCard
                  title="五点描述"
                  icon={<List className="w-4 h-4 text-amber-600" />}
                  dim={result.bullet_points}
                  color="bg-amber-50"
                  dimensionKey="bullet_points"
                  onApplyFix={applyDimensionFix}
                />
                <DimScoreCard
                  title="后台关键词 / Search Terms"
                  icon={<Search className="w-4 h-4 text-teal-600" />}
                  dim={result.backend_keywords}
                  color="bg-teal-50"
                  dimensionKey="backend_keywords"
                  onApplyFix={applyDimensionFix}
                />
              </div>
            </div>
          )}

          {/* Empty State */}
          {!result && !scoring && (
            <Card className="bg-white border-gray-200 p-8 sm:p-12 text-center">
              <div className="relative mx-auto w-20 h-20 mb-6">
                <div className="absolute inset-0 rounded-full bg-gradient-to-br from-teal-500/20 to-teal-500/20 animate-pulse" />
                <div className="absolute inset-2 rounded-full bg-white flex items-center justify-center">
                  <ClipboardCheck className="w-8 h-8 text-gray-600" />
                </div>
              </div>
              <h3 className="text-gray-500 font-medium mb-2">Listing 上新检测</h3>
              <p className="text-gray-600 text-sm max-w-md mx-auto leading-relaxed">
                输入标题、五点、图片、A+和后台搜索关键词，
                系统会输出是否建议上架、风险等级、必改项、缺词和表达错配点
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-8 max-w-2xl mx-auto">
                {[
                  { label: "标题+关键词", icon: <Type className="w-4 h-4" />, color: "text-teal-600 bg-teal-50 border-teal-200" },
                  { label: "主图分析", icon: <ImageIcon className="w-4 h-4" />, color: "text-emerald-600 bg-emerald-50 border-emerald-200" },
                  { label: "A+图文", icon: <FileText className="w-4 h-4" />, color: "text-gold-600 bg-gold-50 border-gold-200" },
                  { label: "五点描述", icon: <List className="w-4 h-4" />, color: "text-amber-600 bg-amber-50 border-amber-200" },
                  { label: "后台关键词", icon: <Search className="w-4 h-4" />, color: "text-teal-600 bg-teal-50 border-teal-200" },
                ].map((item) => (
                  <div key={item.label} className={`${item.color} border rounded-lg p-3 text-center`}>
                    <div className="flex items-center justify-center mb-1">{item.icon}</div>
                    <p className="text-xs font-medium">{item.label}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <NextStepActions
            currentStep="上新检测"
            actions={[
              { label: "进入本品诊断", path: "/listing-diagnosis", variant: "default" },
            ]}
          />
        </div>
      </main>

      {/* History Panel */}
      <HistoryPanel
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onLoadDetail={handleLoadDetail}
      />
    </div>
  );
}
