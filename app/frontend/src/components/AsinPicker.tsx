import { useEffect, useState } from "react";
import { client } from "@/lib/api";
import { withRetry } from "@/lib/api-retry";
import { getActionSnapshots, type ActionSnapshot } from "@/lib/workflow-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { CheckCircle2, Clock, Eye, Package, Search, Star, Database } from "lucide-react";

export interface AsinProduct {
  id: number;
  asin: string;
  title: string;
  bullet_points: string;
  a_plus_content: string;
  search_keywords: string;
  price: number;
  review_count: number;
  rating: number;
  category: string;
}

interface AsinPickerProps {
  onSelect: (product: AsinProduct) => void;
  onSnapshotLoad?: (snapshot: ActionSnapshot, product: AsinProduct) => void;
  snapshotModuleKeys?: string[];
  buttonLabel?: string;
  buttonClassName?: string;
  buttonVariant?: "default" | "outline" | "ghost" | "secondary" | "destructive" | "link";
  buttonSize?: "default" | "sm" | "lg" | "icon";
}

export function AsinPicker({
  onSelect,
  onSnapshotLoad,
  snapshotModuleKeys,
  buttonLabel = "自动保存快照",
  buttonClassName = "",
  buttonVariant = "outline",
  buttonSize = "sm",
}: AsinPickerProps) {
  const [open, setOpen] = useState(false);
  const [products, setProducts] = useState<AsinProduct[]>([]);
  const [snapshots, setSnapshots] = useState<ActionSnapshot[]>([]);
  const [expandedSnapshotAsin, setExpandedSnapshotAsin] = useState("");
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const normalizeTitle = (value?: string) =>
    (value || "").toLowerCase().replace(/\s+/g, " ").trim().slice(0, 120);

  const productFromSnapshot = (snapshot: ActionSnapshot): AsinProduct => {
    const input = (snapshot.input_snapshot || {}) as { listing?: Partial<AsinProduct> };
    const output = (snapshot.output_snapshot || {}) as { listing_title?: string; marketplace?: string };
    const listing = input.listing || {};
    return {
      id: -Number(snapshot.id || 0),
      asin: snapshot.asin || listing.asin || "",
      title: snapshot.title || output.listing_title || listing.title || "未命名快照",
      bullet_points: listing.bullet_points || "",
      a_plus_content: listing.a_plus_content || "",
      search_keywords: listing.search_keywords || "",
      price: Number(listing.price || 0),
      review_count: Number(listing.review_count || 0),
      rating: Number(listing.rating || 0),
      category: listing.category || "",
    };
  };

  useEffect(() => {
    if (open) {
      loadProducts();
      loadSnapshots();
    }
  }, [open]);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const res = await withRetry(() =>
        client.entities.products.query({ sort: "-created_at", limit: 100 })
      );
      setProducts((res?.data?.items || []) as AsinProduct[]);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  const loadSnapshots = async () => {
    try {
      const items = await getActionSnapshots({ limit: 120 });
      setSnapshots(snapshotModuleKeys?.length ? items.filter((item) => snapshotModuleKeys.includes(item.module_key || "")) : items);
    } catch {
      setSnapshots([]);
    }
  };

  const latestSnapshotByAsin = new Map<string, ActionSnapshot>();
  const latestSnapshotByTitle = new Map<string, ActionSnapshot>();
  for (const item of snapshots) {
    if (item.asin && !latestSnapshotByAsin.has(item.asin)) {
      latestSnapshotByAsin.set(item.asin, item);
    }
    const titleKey = normalizeTitle(item.title);
    if (titleKey && !latestSnapshotByTitle.has(titleKey)) {
      latestSnapshotByTitle.set(titleKey, item);
    }
  }

  const productRows = products.map((product) => ({
    kind: "product" as const,
    product,
    snapshot:
      latestSnapshotByAsin.get(product.asin) ||
      latestSnapshotByTitle.get(normalizeTitle(product.title)),
  }));

  const productAsins = new Set(products.map((product) => product.asin).filter(Boolean));
  const productTitles = new Set(products.map((product) => normalizeTitle(product.title)).filter(Boolean));
  const snapshotRows = snapshots
    .filter((snapshot) => {
      const asin = snapshot.asin || "";
      const titleKey = normalizeTitle(snapshot.title);
      return !(asin && productAsins.has(asin)) && !(titleKey && productTitles.has(titleKey));
    })
    .map((snapshot) => ({
      kind: "snapshot" as const,
      product: productFromSnapshot(snapshot),
      snapshot,
    }));

  const rows = [...snapshotRows, ...productRows];

  const filtered = rows.filter(({ product, snapshot }) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      product.asin.toLowerCase().includes(q) ||
      product.title.toLowerCase().includes(q) ||
      (product.category || "").toLowerCase().includes(q) ||
      (snapshot?.module_name || "").toLowerCase().includes(q) ||
      (snapshot?.action_name || "").toLowerCase().includes(q)
    );
  });

  const handleSelect = (product: AsinProduct) => {
    onSelect(product);
    setOpen(false);
    setSearchQuery("");
  };

  const handleSnapshotLoad = (snapshot: ActionSnapshot, product: AsinProduct) => {
    if (onSnapshotLoad) {
      onSnapshotLoad(snapshot, product);
      setOpen(false);
      setSearchQuery("");
      return;
    }
    setExpandedSnapshotAsin(expandedSnapshotAsin === product.asin ? "" : product.asin);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant={buttonVariant}
          size={buttonSize}
          className={`border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-100 bg-transparent ${buttonClassName}`}
        >
          <Database className="w-4 h-4 mr-1.5" />
          {buttonLabel}
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-white border-gray-200 text-gray-900 max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-gray-900">
            <Package className="w-5 h-5 text-brand-600" />
            自动保存快照
          </DialogTitle>
        </DialogHeader>

        <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-700 flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
          自动保存已开启：ASIN抓取、评分、诊断和验证结果会保存为快照；查看快照不会重新生成诊断。
        </div>

        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索 ASIN、标题或类目..."
            className="bg-gray-50 border-gray-200 text-gray-900 pl-10"
          />
        </div>

        <div className="flex-1 overflow-y-auto space-y-1.5 min-h-0 max-h-[50vh] pr-1">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-5 h-5 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
              <span className="ml-2 text-sm text-gray-500">加载中...</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-8">
              <Package className="w-10 h-10 text-gray-600 mx-auto mb-2" />
              <p className="text-sm text-gray-500">
                {rows.length === 0
                  ? "暂无可用快照，请先完成ASIN抓取或诊断分析"
                  : "没有匹配的产品"}
              </p>
            </div>
          ) : (
            filtered.map(({ product, snapshot, kind }) => {
              const rowKey = product.asin || `snapshot-${snapshot?.id || product.id}`;
              const expanded = expandedSnapshotAsin === rowKey;
              return (
                <div
                  key={`${kind}-${rowKey}`}
                  onClick={() => {
                    if (snapshot && onSnapshotLoad) {
                      handleSnapshotLoad(snapshot, product);
                    } else {
                      handleSelect(product);
                    }
                  }}
                  className="rounded-lg bg-gray-50 border border-gray-100 hover:border-brand-200 hover:bg-brand-500/5 transition-all group cursor-pointer"
                >
                  <div className="w-full text-left p-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0">
                        <Package className="w-4 h-4 text-brand-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          {product.asin ? (
                            <span className="text-xs font-mono text-brand-600 bg-brand-50 px-1.5 py-0.5 rounded">
                              {product.asin}
                            </span>
                          ) : (
                            <span className="text-xs text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded">
                              快照记录
                            </span>
                          )}
                          {kind === "snapshot" && (
                            <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
                              未入产品库
                            </span>
                          )}
                          {product.category && (
                            <span className="text-[10px] text-gray-500">
                              {product.category}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 truncate group-hover:text-gray-900 transition-colors">
                          {product.title}
                        </p>
                        <div className="flex items-center gap-3 mt-1 text-[10px] text-gray-500">
                          {product.price > 0 && (
                            <span className="text-emerald-600">
                              ${product.price}
                            </span>
                          )}
                          {product.rating > 0 && (
                            <span className="flex items-center gap-0.5 text-amber-600">
                              <Star className="w-2.5 h-2.5" /> {product.rating}
                            </span>
                          )}
                          {product.review_count > 0 && (
                            <span>{product.review_count} 评价</span>
                          )}
                          {snapshot && (
                            <span className="text-emerald-600">点击打开完整快照</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="px-3 pb-3 pl-14">
                    {snapshot ? (
                      <div className="rounded-md border border-emerald-100 bg-white px-2 py-1.5">
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <span className="text-[11px] text-emerald-700 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            已保存快照：{snapshot.module_name} / {snapshot.action_name}
                          </span>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSnapshotLoad(snapshot, product);
                              }}
                              className="rounded-md bg-brand-600 px-2 py-1 text-[11px] text-white hover:bg-brand-500 inline-flex items-center gap-1"
                            >
                              <Eye className="w-3 h-3" />
                              打开完整快照
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSelect(product);
                              }}
                              className="text-[11px] text-gray-500 hover:text-brand-700"
                            >
                              回填表单
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setExpandedSnapshotAsin(expanded ? "" : rowKey);
                              }}
                              className="text-[11px] text-gray-500 hover:text-brand-700"
                            >
                              {expanded ? "收起原始数据" : "原始数据"}
                            </button>
                          </div>
                        </div>
                        {expanded && (
                          <pre className="mt-2 max-h-36 overflow-auto rounded bg-gray-50 border border-gray-100 p-2 text-[10px] text-gray-600 whitespace-pre-wrap">
                            {JSON.stringify(snapshot.output_snapshot || snapshot.input_snapshot || {}, null, 2)}
                          </pre>
                        )}
                      </div>
                    ) : (
                      <div className="rounded-md border border-amber-100 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-700 flex items-center justify-between gap-2">
                        <span>暂无快照：选择后开始分析/诊断会自动保存</span>
                        <button
                          type="button"
                          onClick={() => handleSelect(product)}
                          className="text-brand-600 hover:text-brand-700"
                        >
                          回填ASIN
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
