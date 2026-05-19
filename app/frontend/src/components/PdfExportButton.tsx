import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Download, Loader2 } from "lucide-react";

export function PdfExportButton() {
  const [exporting, setExporting] = useState(false);
  const [progress, setProgress] = useState("");

  const handleExport = useCallback(async () => {
    if (exporting) return;
    setExporting(true);
    setProgress("正在准备报告...");

    try {
      const html2canvas = (await import("html2canvas-pro")).default;
      const { jsPDF } = await import("jspdf");

      // Use landscape A4 for better content fit
      const pdf = new jsPDF("l", "mm", "a4");
      const pageWidth = 297; // A4 landscape width in mm
      const pageHeight = 210; // A4 landscape height in mm
      const margin = 8;
      const contentWidth = pageWidth - margin * 2;
      const contentHeight = pageHeight - margin * 2;

      // Collect all sections to capture individually
      const sectionIds = [
        "pdf-hero",
        "pdf-section-1",
        "pdf-section-2",
        "pdf-section-3",
        "pdf-section-4",
        "pdf-section-5",
        "pdf-footer",
      ];

      const sections = sectionIds
        .map((id) => document.getElementById(id))
        .filter(Boolean) as HTMLElement[];

      if (sections.length === 0) {
        throw new Error("No report sections found");
      }

      let isFirstPage = true;

      for (let i = 0; i < sections.length; i++) {
        const section = sections[i];
        setProgress(`正在渲染第 ${i + 1}/${sections.length} 部分...`);

        const canvas = await html2canvas(section, {
          scale: 2,
          useCORS: true,
          allowTaint: true,
          backgroundColor: "#f9fafb",
          logging: false,
          windowWidth: 1280,
          onclone: (_clonedDoc, clonedEl) => {
            clonedEl.style.width = "1280px";
          },
        });

        const imgData = canvas.toDataURL("image/jpeg", 0.92);
        const imgAspect = canvas.width / canvas.height;

        // Calculate how to fit this section's image into pages
        // Scale image to fit content width
        const scaledWidth = contentWidth;
        const scaledHeight = contentWidth / imgAspect;

        if (scaledHeight <= contentHeight) {
          // Section fits on one page
          if (!isFirstPage) pdf.addPage();
          isFirstPage = false;

          // Add dark background
          pdf.setFillColor(10, 15, 28);
          pdf.rect(0, 0, pageWidth, pageHeight, "F");

          // Center vertically
          const yOffset = margin + (contentHeight - scaledHeight) / 2;
          pdf.addImage(imgData, "JPEG", margin, yOffset, scaledWidth, scaledHeight);
        } else {
          // Section is taller than one page - split into multiple pages
          const totalPages = Math.ceil(scaledHeight / contentHeight);

          for (let p = 0; p < totalPages; p++) {
            if (!isFirstPage) pdf.addPage();
            isFirstPage = false;

            // Add dark background
            pdf.setFillColor(10, 15, 28);
            pdf.rect(0, 0, pageWidth, pageHeight, "F");

            // Calculate which portion of the image to show
            const sourceY = (p * contentHeight / scaledHeight) * canvas.height;
            const sourceH = (contentHeight / scaledHeight) * canvas.height;
            const remainingScaledH = scaledHeight - p * contentHeight;
            const thisPageH = Math.min(contentHeight, remainingScaledH);

            // Create a temporary canvas for this page slice
            const sliceCanvas = document.createElement("canvas");
            sliceCanvas.width = canvas.width;
            sliceCanvas.height = Math.min(sourceH, canvas.height - sourceY);
            const ctx = sliceCanvas.getContext("2d");
            if (ctx) {
              ctx.fillStyle = "#f9fafb";
              ctx.fillRect(0, 0, sliceCanvas.width, sliceCanvas.height);
              ctx.drawImage(
                canvas,
                0, sourceY,
                canvas.width, sliceCanvas.height,
                0, 0,
                sliceCanvas.width, sliceCanvas.height
              );
            }

            const sliceData = sliceCanvas.toDataURL("image/jpeg", 0.92);
            pdf.addImage(sliceData, "JPEG", margin, margin, scaledWidth, thisPageH);
          }
        }
      }

      setProgress("正在下载...");
      pdf.save("AlignX-Deep-Research-Report.pdf");
      setProgress("");
    } catch (err) {
      console.error("PDF export failed:", err);
      setProgress("导出失败，请重试");
      setTimeout(() => setProgress(""), 3000);
    } finally {
      setExporting(false);
    }
  }, [exporting]);

  return (
    <div className="flex items-center gap-3">
      <Button
        onClick={handleExport}
        disabled={exporting}
        className="bg-gradient-to-r from-brand-600 to-gold-600 hover:from-brand-500 hover:to-gold-500 text-white border-0 shadow-lg shadow-brand-200 px-6 py-2.5 text-sm font-semibold transition-all duration-300 disabled:opacity-60"
      >
        {exporting ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            导出中...
          </>
        ) : (
          <>
            <Download className="w-4 h-4 mr-2" />
            导出PDF报告
          </>
        )}
      </Button>
      {progress && (
        <span className="text-xs text-brand-600 animate-pulse">{progress}</span>
      )}
    </div>
  );
}