import { useState } from "react";
import { MessageSquare, Send, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { getAuthHeaders } from "@/lib/auth-headers";
import { getAPIBaseURL } from "@/lib/config";

interface FeedbackDialogProps {
  triggerClassName?: string;
  variant?: "default" | "outline" | "ghost";
}

export function FeedbackDialog({ triggerClassName = "", variant = "outline" }: FeedbackDialogProps) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    const text = content.trim();
    if (text.length < 5) {
      toast.error("请至少输入5个字，方便我们定位问题");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${getAPIBaseURL()}/api/v1/action-snapshots`, {
        method: "POST",
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          module_key: "user_feedback",
          module_name: "用户反馈",
          action_key: "feedback_message",
          action_name: "使用问题反馈",
          input_snapshot: {
            content: text,
            path: window.location.pathname,
            user_agent: navigator.userAgent,
          },
          output_snapshot: {
            status: "submitted",
          },
          data_source: "user_input",
          confidence: "high",
          ai_called: false,
        }),
      });
      if (!res.ok) throw new Error("反馈提交失败，请稍后重试");
      toast.success("反馈已提交，我们会在内测优化中处理");
      setContent("");
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "反馈提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={variant} className={triggerClassName}>
          <MessageSquare className="w-4 h-4 mr-2" />
          反馈问题
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>使用问题反馈</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="请描述你遇到的问题、页面位置、期望结果或优化建议..."
            className="min-h-[150px]"
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button onClick={submit} disabled={submitting} className="bg-brand-600 hover:bg-brand-500 text-white">
              {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
              提交反馈
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
