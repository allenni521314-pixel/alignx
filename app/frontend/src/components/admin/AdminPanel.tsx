/**
 * AdminPanel - Super admin management panel, designed to be embedded inside
 * the Settings page or other parent containers. It does NOT render its own
 * sidebar/layout; parent is responsible for layout.
 *
 * Features:
 * - Platform overview stats
 * - Search and list all sellers
 * - Drill into seller detail (ASIN scores / products / listings)
 * - Promote / demote user roles
 */
import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { AIModelStatusPanel } from "@/components/admin/AIModelStatusPanel";
import {
  getAdminOverview,
  listAllSellers,
  getSellerProducts,
  getSellerAsinScores,
  getSellerListings,
  updateUserRole,
  type SellerInfo,
  type AdminOverview,
  type SellerAsinScore,
  type SellerProduct,
  type SellerListing,
} from "@/lib/admin-api";
import {
  Users,
  Package,
  Award,
  FileText,
  Search,
  ShieldCheck,
  ChevronRight,
  ArrowLeft,
  UserCog,
} from "lucide-react";

type TabType = "asin-scores" | "products" | "listings";

export default function AdminPanel() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [sellers, setSellers] = useState<SellerInfo[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const [selectedSeller, setSelectedSeller] = useState<SellerInfo | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("asin-scores");
  const [asinScores, setAsinScores] = useState<SellerAsinScore[]>([]);
  const [products, setProducts] = useState<SellerProduct[]>([]);
  const [listings, setListings] = useState<SellerListing[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    loadOverview();
    loadSellers();
  }, []);

  const loadOverview = async () => {
    try {
      const data = await getAdminOverview();
      setOverview(data);
    } catch (e) {
      console.error(e);
    }
  };

  const loadSellers = async (searchText?: string) => {
    setLoading(true);
    try {
      const data = await listAllSellers(searchText);
      setSellers(data);
    } catch (e) {
      console.error(e);
      toast.error("加载卖家列表失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    loadSellers(search.trim());
  };

  const loadSellerDetail = async (seller: SellerInfo) => {
    setSelectedSeller(seller);
    setDetailLoading(true);
    try {
      const [scoresRes, productsRes, listingsRes] = await Promise.all([
        getSellerAsinScores(seller.id).catch(() => ({ items: [], total: 0 })),
        getSellerProducts(seller.id).catch(() => ({ items: [], total: 0 })),
        getSellerListings(seller.id).catch(() => ({ items: [], total: 0 })),
      ]);
      setAsinScores(scoresRes.items);
      setProducts(productsRes.items);
      setListings(listingsRes.items);
    } catch (e) {
      console.error(e);
      toast.error("加载卖家数据失败");
    } finally {
      setDetailLoading(false);
    }
  };

  const handlePromote = async (
    userId: string,
    role: "user" | "admin" | "super_admin"
  ) => {
    try {
      await updateUserRole(userId, role);
      toast.success(`角色已更新为 ${role}`);
      loadSellers(search.trim() || undefined);
      if (selectedSeller?.id === userId) {
        setSelectedSeller({ ...selectedSeller, role });
      }
    } catch (e) {
      console.error(e);
      toast.error("角色更新失败");
    }
  };

  const statCards = useMemo(
    () => [
      {
        label: "注册卖家",
        value: overview?.total_users || 0,
        icon: Users,
        color: "text-brand-600",
        bg: "bg-brand-50",
      },
      {
        label: "全部产品",
        value: overview?.total_products || 0,
        icon: Package,
        color: "text-teal-600",
        bg: "bg-teal-50",
      },
      {
        label: "6D 评分",
        value: overview?.total_asin_scores || 0,
        icon: Award,
        color: "text-gold-600",
        bg: "bg-gold-50",
      },
      {
        label: "机会池 (≥70分)",
        value: overview?.qualified_count || 0,
        icon: ShieldCheck,
        color: "text-emerald-600",
        bg: "bg-emerald-50",
      },
      {
        label: "Listing 数量",
        value: overview?.total_listings || 0,
        icon: FileText,
        color: "text-amber-600",
        bg: "bg-amber-50",
      },
    ],
    [overview]
  );

  // Seller detail view
  if (selectedSeller) {
    return (
      <div>
        <div className="mb-5">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSelectedSeller(null)}
            className="mb-3 -ml-2 text-gray-600"
          >
            <ArrowLeft className="w-4 h-4 mr-1" /> 返回卖家列表
          </Button>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h3 className="text-lg sm:text-xl font-bold text-gray-900">
                {selectedSeller.name || selectedSeller.email}
              </h3>
              <p className="text-xs text-gray-500 mt-1 font-mono">
                {selectedSeller.id}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge
                className={
                  selectedSeller.role === "super_admin"
                    ? "bg-gold-100 text-gold-700"
                    : selectedSeller.role === "admin"
                      ? "bg-brand-100 text-brand-700"
                      : "bg-gray-100 text-gray-700"
                }
              >
                {selectedSeller.role}
              </Badge>
              {selectedSeller.role !== "super_admin" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    handlePromote(selectedSeller.id, "super_admin")
                  }
                >
                  <UserCog className="w-3.5 h-3.5 mr-1" />
                  提升为超管
                </Button>
              )}
              {selectedSeller.role === "super_admin" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handlePromote(selectedSeller.id, "user")}
                >
                  降级为普通
                </Button>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-5">
          <Card className="p-3 sm:p-4">
            <p className="text-xs text-gray-500">产品</p>
            <p className="text-xl sm:text-2xl font-bold text-gray-900 mt-1">
              {selectedSeller.product_count}
            </p>
          </Card>
          <Card className="p-3 sm:p-4">
            <p className="text-xs text-gray-500">6D 评分</p>
            <p className="text-xl sm:text-2xl font-bold text-gray-900 mt-1">
              {selectedSeller.asin_score_count}
            </p>
          </Card>
          <Card className="p-3 sm:p-4">
            <p className="text-xs text-gray-500">Listing</p>
            <p className="text-xl sm:text-2xl font-bold text-gray-900 mt-1">
              {selectedSeller.listing_count}
            </p>
          </Card>
        </div>

        <div className="flex border-b border-gray-200 mb-4 overflow-x-auto">
          {(
            [
              { key: "asin-scores", label: "ASIN 6D评分" },
              { key: "products", label: "产品" },
              { key: "listings", label: "Listing" },
            ] as { key: TabType; label: string }[]
          ).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.key
                  ? "border-brand-600 text-brand-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {detailLoading ? (
          <div className="space-y-2 animate-pulse">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-14 bg-gray-50 rounded-lg" />
            ))}
          </div>
        ) : (
          <Card className="overflow-hidden">
            {activeTab === "asin-scores" && (
              <div className="divide-y divide-gray-100 max-h-[500px] overflow-y-auto">
                {asinScores.length === 0 ? (
                  <div className="p-8 text-center text-gray-400 text-sm">
                    暂无评分数据
                  </div>
                ) : (
                  asinScores.map((s) => (
                    <div
                      key={s.id}
                      className="p-3 flex items-center gap-3 hover:bg-gray-50"
                    >
                      <span className="font-mono text-xs bg-brand-50 text-brand-700 px-2 py-1 rounded">
                        {s.asin}
                      </span>
                      <span className="flex-1 text-sm text-gray-900 truncate">
                        {s.product_title || "-"}
                      </span>
                      <span
                        className={`text-sm font-bold ${
                          s.qualified ? "text-emerald-600" : "text-amber-600"
                        }`}
                      >
                        {s.total_score}分
                      </span>
                      {s.qualified && (
                        <Badge className="bg-emerald-100 text-emerald-700 text-[10px]">
                          机会池
                        </Badge>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === "products" && (
              <div className="divide-y divide-gray-100 max-h-[500px] overflow-y-auto">
                {products.length === 0 ? (
                  <div className="p-8 text-center text-gray-400 text-sm">
                    暂无产品
                  </div>
                ) : (
                  products.map((p) => (
                    <div
                      key={p.id}
                      className="p-3 flex items-center gap-3 hover:bg-gray-50"
                    >
                      {p.asin && (
                        <span className="font-mono text-xs bg-teal-50 text-teal-700 px-2 py-1 rounded">
                          {String(p.asin)}
                        </span>
                      )}
                      <span className="flex-1 text-sm text-gray-900 truncate">
                        {String(p.title || "-")}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === "listings" && (
              <div className="divide-y divide-gray-100 max-h-[500px] overflow-y-auto">
                {listings.length === 0 ? (
                  <div className="p-8 text-center text-gray-400 text-sm">
                    暂无 Listing
                  </div>
                ) : (
                  listings.map((l) => (
                    <div
                      key={l.id}
                      className="p-3 flex items-center gap-3 hover:bg-gray-50"
                    >
                      {l.asin && (
                        <span className="font-mono text-xs bg-teal-50 text-teal-700 px-2 py-1 rounded">
                          {String(l.asin)}
                        </span>
                      )}
                      <span className="flex-1 text-sm text-gray-900 truncate">
                        {String(l.title || "-")}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </Card>
        )}
      </div>
    );
  }

  // Main list view
  return (
    <div>
      {/* Overview stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-5">
        {statCards.map((s) => (
          <Card key={s.label} className="p-3 sm:p-4">
            <div
              className={`w-8 h-8 rounded-lg ${s.bg} flex items-center justify-center mb-2 sm:mb-3`}
            >
              <s.icon className={`w-4 h-4 ${s.color}`} />
            </div>
            <p className="text-xl sm:text-2xl font-bold text-gray-900">
              {s.value}
            </p>
            <p className="text-xs text-gray-500 mt-1">{s.label}</p>
          </Card>
        ))}
      </div>

      <AIModelStatusPanel />

      {/* Search */}
      <Card className="p-3 sm:p-4 mb-4">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <Input
              placeholder="按邮箱、姓名或ID搜索卖家..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="pl-9"
            />
          </div>
          <Button onClick={handleSearch}>搜索</Button>
        </div>
      </Card>

      {/* Sellers list */}
      <Card className="overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <h4 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Users className="w-4 h-4 text-gray-500" />
            全部卖家
            <span className="text-xs font-normal text-gray-400">
              ({sellers.length})
            </span>
          </h4>
        </div>

        {loading ? (
          <div className="p-4 space-y-2 animate-pulse">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 bg-gray-50 rounded-lg" />
            ))}
          </div>
        ) : sellers.length === 0 ? (
          <div className="p-12 text-center text-gray-400 text-sm">
            暂无卖家数据
          </div>
        ) : (
          <div className="divide-y divide-gray-100 max-h-[600px] overflow-y-auto">
            {sellers.map((seller) => (
              <button
                key={seller.id}
                onClick={() => loadSellerDetail(seller)}
                className="w-full p-3 sm:p-4 flex items-center gap-3 hover:bg-gray-50 text-left transition-colors"
              >
                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-brand-100 to-gold-100 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-bold text-brand-700">
                    {(seller.name || seller.email || "?")
                      .substring(0, 2)
                      .toUpperCase()}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900 truncate">
                      {seller.name || seller.email}
                    </span>
                    <Badge
                      className={`text-[10px] border-0 ${
                        seller.role === "super_admin"
                          ? "bg-gold-100 text-gold-700"
                          : seller.role === "admin"
                            ? "bg-brand-100 text-brand-700"
                            : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {seller.role}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5 truncate">
                    {seller.email}
                  </p>
                </div>
                <div className="hidden sm:flex items-center gap-4 text-xs text-gray-500 flex-shrink-0">
                  <div className="text-center">
                    <p className="font-semibold text-gray-900">
                      {seller.product_count}
                    </p>
                    <p>产品</p>
                  </div>
                  <div className="text-center">
                    <p className="font-semibold text-gray-900">
                      {seller.asin_score_count}
                    </p>
                    <p>评分</p>
                  </div>
                  <div className="text-center">
                    <p className="font-semibold text-gray-900">
                      {seller.listing_count}
                    </p>
                    <p>Listing</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
              </button>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
