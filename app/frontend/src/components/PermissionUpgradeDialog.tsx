import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Lock } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface PermissionUpgradeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  feature?: "competitor" | "alignment" | "ad" | "review" | "quota";
}

const copy = {
  competitor: "竞品诊断属于专业版能力，升级后可对比 Top 竞品与本品 Listing 的表达差距。",
  alignment: "完整对齐度分析属于专业版能力，包含评论需求对齐度、Cosmo 语义对齐度和因果转化对齐度。",
  ad: "广告验证属于专业版能力，用于验证 Listing 诊断结论是否成立。",
  review: "数据回流属于专业版能力，用于沉淀广告验证结果并生成下一轮优化动作。",
  quota: "你的当前套餐额度已使用完，可升级套餐或购买加量包继续使用。",
};

export function PermissionUpgradeDialog({
  open,
  onOpenChange,
  feature = "competitor",
}: PermissionUpgradeDialogProps) {
  const navigate = useNavigate();
  const isQuota = feature === "quota";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white border-gray-200 text-gray-900">
        <DialogHeader>
          <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center mb-2">
            <Lock className="w-5 h-5 text-brand-600" />
          </div>
          <DialogTitle>{isQuota ? "本月额度已用完" : "该功能需要升级套餐"}</DialogTitle>
          <DialogDescription className="text-gray-500 leading-relaxed">
            {copy[feature]}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            稍后再说
          </Button>
          <Button
            className="bg-brand-600 hover:bg-brand-500 text-white"
            onClick={() => {
              onOpenChange(false);
              navigate("/pricing");
            }}
          >
            {isQuota ? "升级套餐 / 购买加量包" : "查看套餐"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
