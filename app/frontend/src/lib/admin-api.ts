/**
 * Super Admin API helpers - cross-tenant data viewing.
 */
import axios from "axios";
import { getAuthHeaders } from "@/lib/auth-headers";

export interface SellerInfo {
  id: string;
  email: string;
  name: string | null;
  role: string;
  product_count: number;
  asin_score_count: number;
  listing_count: number;
}

export interface AdminMe {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_super_admin: boolean;
}

export interface AdminOverview {
  total_users: number;
  total_products: number;
  total_asin_scores: number;
  qualified_count: number;
  total_listings: number;
}

export interface AdminAIModelItem {
  module: string;
  env_key: string;
  model: string;
  provider: string;
  configured: boolean;
  endpoint: string;
  purpose: string;
  source: string;
  input_cost_per_1m_cny: number;
  output_cost_per_1m_cny: number;
}

export interface AdminAIModelStatus {
  provider: string;
  api_mode: string;
  text_base_url: string;
  vision_base_url: string;
  gateway_configured: boolean;
  vision_configured: boolean;
  embedding_configured: boolean;
  rerank_configured: boolean;
  models: AdminAIModelItem[];
  usage_7d: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated_cost_cny: number;
    calls: number;
    by_model: Array<{
      provider: string;
      model: string;
      module: string;
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
      estimated_cost_cny: number;
      calls: number;
    }>;
  };
  recharge_links: Array<{ provider: string; url: string }>;
  legacy_alias_policy: string;
  invocation_contract?: Array<{
    key: string;
    name: string;
    steps: Array<{
      key: string;
      owner: string;
      purpose: string;
      output_contract: string;
      blocks_final_score: boolean;
    }>;
  }>;
}

export interface AdminAIModelProbe {
  ok: boolean;
  checked_at: number;
  probes: Array<{
    name: string;
    provider: string;
    model: string;
    ok: boolean;
    latency_ms: number;
    detail?: string;
    error?: string;
  }>;
}

export interface SellerAsinScore {
  id: number;
  asin: string;
  marketplace: string;
  product_title: string;
  total_score: number;
  qualified: boolean;
  dimension_scores: {
    demand: number;
    scenario: number;
    competition: number;
    profit: number;
    trend: number;
  };
  created_at: string | null;
}

export interface SellerProduct {
  id: number;
  asin?: string;
  title?: string;
  user_id: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface SellerListing {
  id: number;
  asin?: string;
  title?: string;
  user_id: string;
  [key: string]: unknown;
}

const headers = () => getAuthHeaders();

export async function getAdminMe(): Promise<AdminMe | null> {
  try {
    const res = await axios.get("/api/v1/admin/me", { headers: headers() });
    return res.data;
  } catch {
    return null;
  }
}

export async function getAdminOverview(): Promise<AdminOverview> {
  const res = await axios.get("/api/v1/admin/overview", { headers: headers() });
  return res.data;
}

export async function getAdminAIModels(): Promise<AdminAIModelStatus> {
  const res = await axios.get("/api/v1/admin/ai-models", { headers: headers() });
  return res.data;
}

export async function probeAdminAIModels(): Promise<AdminAIModelProbe> {
  const res = await axios.post("/api/v1/admin/ai-models/probe", {}, { headers: headers() });
  return res.data;
}

export async function listAllSellers(search?: string): Promise<SellerInfo[]> {
  const res = await axios.get("/api/v1/admin/sellers", {
    headers: headers(),
    params: search ? { search } : {},
  });
  return res.data || [];
}

export async function getSellerProducts(
  sellerId: string,
  skip = 0,
  limit = 50
): Promise<{ items: SellerProduct[]; total: number }> {
  const res = await axios.get(`/api/v1/admin/sellers/${sellerId}/products`, {
    headers: headers(),
    params: { skip, limit },
  });
  return res.data;
}

export async function getSellerAsinScores(
  sellerId: string,
  skip = 0,
  limit = 100
): Promise<{ items: SellerAsinScore[]; total: number }> {
  const res = await axios.get(
    `/api/v1/admin/sellers/${sellerId}/asin-scores`,
    {
      headers: headers(),
      params: { skip, limit },
    }
  );
  return res.data;
}

export async function getSellerListings(
  sellerId: string,
  skip = 0,
  limit = 50
): Promise<{ items: SellerListing[]; total: number }> {
  const res = await axios.get(`/api/v1/admin/sellers/${sellerId}/listings`, {
    headers: headers(),
    params: { skip, limit },
  });
  return res.data;
}

export async function updateUserRole(
  userId: string,
  role: "user" | "admin" | "super_admin"
): Promise<{ id: string; email: string; role: string }> {
  const res = await axios.post(
    `/api/v1/admin/users/${userId}/role`,
    { role },
    { headers: headers() }
  );
  return res.data;
}
