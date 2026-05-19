import { useEffect, useRef } from "react";

interface ScoreData {
  label: string;
  key: string;
  value: number;
}

interface RadarDataSet {
  label: string;
  scores: ScoreData[];
  color: string;
  fillColor: string;
}

interface RadarChartMultiProps {
  datasets: RadarDataSet[];
  size?: number;
}

const DIMENSIONS = [
  { key: "functionality", label: "功能表达" },
  { key: "emotional", label: "场景表达" },
  { key: "scenario", label: "身份适配" },
  { key: "user_profile", label: "心理利益" },
  { key: "differentiation", label: "差异化" },
  { key: "market_trend", label: "市场趋势" },
  { key: "product_identity", label: "产品身份" },
  { key: "compatibility", label: "兼容搭配" },
  { key: "subjective_properties", label: "主观属性" },
  { key: "risk_elimination", label: "风险消除" },
];

export function RadarChartMulti({ datasets, size = 300 }: RadarChartMultiProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const activeDimensions = datasets[0]?.scores?.length
      ? datasets[0].scores.map((score) => ({ key: score.key, label: score.label }))
      : DIMENSIONS;
    const radius = size * 0.28;
    const sides = activeDimensions.length;
    const angleStep = (Math.PI * 2) / sides;
    const startAngle = -Math.PI / 2;

    // Clear
    ctx.clearRect(0, 0, size, size);

    // Draw grid rings
    const rings = [0.2, 0.4, 0.6, 0.8, 1.0];
    rings.forEach((ring) => {
      ctx.beginPath();
      for (let i = 0; i <= sides; i++) {
        const angle = startAngle + i * angleStep;
        const x = cx + Math.cos(angle) * radius * ring;
        const y = cy + Math.sin(angle) * radius * ring;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = "rgba(99,102,241,0.18)";
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    // Draw axis lines
    for (let i = 0; i < sides; i++) {
      const angle = startAngle + i * angleStep;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius);
      ctx.strokeStyle = "rgba(99,102,241,0.16)";
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // Draw labels and single-dataset scores
    ctx.font = "600 11px 'Inter', sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    activeDimensions.forEach((dim, i) => {
      const angle = startAngle + i * angleStep;
      const labelRadius = radius + 36;
      const x = cx + Math.cos(angle) * labelRadius;
      const y = cy + Math.sin(angle) * labelRadius;
      const score = datasets.length === 1
        ? datasets[0].scores.find((s) => s.key === dim.key)?.value
        : undefined;
      ctx.fillStyle = "#374151";
      ctx.fillText(dim.label, x, y - (score !== undefined ? 7 : 0));
      if (score !== undefined) {
        ctx.font = "700 12px 'Inter', sans-serif";
        ctx.fillStyle = score >= 80 ? "#059669" : score >= 60 ? "#0f2a24" : "#dc2626";
        ctx.fillText(`${Math.round(score)}分`, x, y + 9);
        ctx.font = "600 11px 'Inter', sans-serif";
      }
    });

    // Draw scale labels
    ctx.font = "9px 'Inter', sans-serif";
    ctx.fillStyle = "rgba(107,114,128,0.65)";
    rings.forEach((ring) => {
      const y = cy - radius * ring;
      ctx.fillText(`${Math.round(ring * 100)}`, cx + 10, y + 2);
    });

    // Draw data polygons
    datasets.forEach((dataset) => {
      ctx.beginPath();
      activeDimensions.forEach((dim, i) => {
        const score = dataset.scores.find((s) => s.key === dim.key);
        const value = score ? score.value / 100 : 0;
        const angle = startAngle + i * angleStep;
        const x = cx + Math.cos(angle) * radius * value;
        const y = cy + Math.sin(angle) * radius * value;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.closePath();

      // Fill
      ctx.fillStyle = dataset.fillColor;
      ctx.fill();

      // Stroke
      ctx.strokeStyle = dataset.color;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Draw points
      activeDimensions.forEach((dim, i) => {
        const score = dataset.scores.find((s) => s.key === dim.key);
        const value = score ? score.value / 100 : 0;
        const angle = startAngle + i * angleStep;
        const x = cx + Math.cos(angle) * radius * value;
        const y = cy + Math.sin(angle) * radius * value;

        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fillStyle = dataset.color;
        ctx.fill();
        ctx.strokeStyle = "#f9fafb";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      });
    });
  }, [datasets, size]);

  return (
    <div className="flex flex-col items-center gap-3">
      <canvas ref={canvasRef} style={{ width: size, height: size }} />
      {datasets.length > 1 && (
        <div className="flex flex-wrap gap-4 justify-center">
          {datasets.map((ds, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-gray-500">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: ds.color }}
              />
              <span>{ds.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export { DIMENSIONS };
export type { RadarDataSet, ScoreData };
