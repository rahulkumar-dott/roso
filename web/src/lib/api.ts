import type {
  AdminContentResponse,
  AdminDestinationsResponse,
  AdminOverview,
  AdminPendingDestinationsResponse,
  AdminProductDebug,
  AdminProductsResponse,
  AdminPublishingResponse,
  AdminSimilarityResponse,
  AdminSiteConfigResponse,
  AuditLogResponse,
  CityPicksResponse,
  DestinationsTreeResponse,
  PublishedListResponse,
  PublishedRecord,
} from "./types";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
export const BROWSER_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

async function apiGet<T>(path: string): Promise<T | null> {
  const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`API ${path} returned ${res.status}`);
  }
  return (await res.json()) as T;
}

export function getCityPicks(cityId: string) {
  return apiGet<CityPicksResponse>(`/cities/${encodeURIComponent(cityId)}/picks`);
}

export function getPublishedRecord(entityId: string) {
  return apiGet<PublishedRecord>(`/published/${encodeURIComponent(entityId)}`);
}

export const getPublishedTour = getPublishedRecord;

export function getPublishedList(limit = 100) {
  return apiGet<PublishedListResponse>(`/published?limit=${limit}`);
}

export function getDestinationsTree() {
  return apiGet<DestinationsTreeResponse>("/destinations/tree");
}

export function getAdminOverview() {
  return apiGet<AdminOverview>("/admin/overview");
}

export function getAdminDestinations() {
  return apiGet<AdminDestinationsResponse>("/admin/destinations");
}

export function getAdminProducts() {
  return apiGet<AdminProductsResponse>("/admin/products");
}

export function getAdminContent() {
  return apiGet<AdminContentResponse>("/admin/content");
}

export function getAdminPublishing() {
  return apiGet<AdminPublishingResponse>("/admin/publishing");
}

export function getAdminPendingDestinations() {
  return apiGet<AdminPendingDestinationsResponse>("/admin/destinations/pending");
}

export function getAdminProductDebug(entityId: string) {
  return apiGet<AdminProductDebug>(`/admin/products/${encodeURIComponent(entityId)}/debug`);
}

export function getAdminContentSimilarity() {
  return apiGet<AdminSimilarityResponse>("/admin/content/similarity");
}

export function getAdminSiteConfig() {
  return apiGet<AdminSiteConfigResponse>("/admin/site-config");
}

export function getAuditLog(limit = 50) {
  return apiGet<AuditLogResponse>(`/admin/audit-log?limit=${limit}`);
}
