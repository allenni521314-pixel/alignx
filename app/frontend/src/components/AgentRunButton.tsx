import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles, CheckCircle2, AlertTriangle } from "lucide-react";
import axios from "axios";
import { getAuthHeaders } from "@/lib/auth-headers";
import { toast } from "sonner";

interface Props {
  node: string;
  label: string;
  idleLabel?: string;
  doneLabel?: string;
  depth?: "light" | "standard" | "deep";
  variant?: "default" | "outline" | "ghost";
  size?: "sm" | "default";
}

export function AgentRunButton({ node, label, idleLabel, doneLabel, depth = "standard", variant = "outline", size = "sm" }: Props) {
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");

  const run = useCallback(async () => {
    setStatus("running");
    try {
      await axios.post("/api/v1/workflow-chain/current/agent-node",
        { node, depth }, { headers: getAuthHeaders() }
      );
      setStatus("done");
      toast.success(`${label} 分析完成`);
    } catch {
      setStatus("error");
    }
  }, [node, depth, label]);

  return (
    <Button variant={variant} size={size} onClick={run} disabled={status === "running"}
      className={`gap-1.5 ${status === "done" ? "text-emerald-600 border-emerald-200" : status === "error" ? "text-red-500" : ""}`}>
      {status === "running" ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
        : status === "done" ? <CheckCircle2 className="w-3.5 h-3.5" />
        : status === "error" ? <AlertTriangle className="w-3.5 h-3.5" />
        : <Sparkles className="w-3.5 h-3.5" />}
      {status === "running" ? "运行中..." : status === "done" ? doneLabel || `${label} 已完成` : status === "error" ? "重试" : idleLabel || `运行${label}`}
    </Button>
  );
}
