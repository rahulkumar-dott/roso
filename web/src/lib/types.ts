export interface AudienceVariant {
  audience: string;
  snippet_text: string;
}

export interface FaqItem {
  question: string;
  answer: string;
}

export interface ModelCInfo {
  product_id: string;
  in_pool: boolean;
  in_set: boolean;
  quality_score: number;
  completeness_score: number;
  reasons: string[];
  archetypes: string[];
  winner_slots: string[];
  competed_against: string[];
}

export interface TopCity {
  entity_id: string;
  name: string;
  canonical_url: string;
}

export interface TopRegion {
  entity_id: string;
  name: string;
}

export interface HeroImage {
  url: string;
  alt_text: string;
  source_class: "A" | "B" | "C";
  rights_status: string;
  indexable: boolean;
  generator: string;
  generated_at: string;
}

export interface PublishedContent {
  h1: string;
  meta_title: string;
  meta_description: string;
  canonical_url: string;
  images?: string[];
  primary_image?: string | null;
  price_from?: number | null;
  currency?: string | null;
  overview?: string;
  facts?: string[];
  about_rosotravel?: string;
  local_tips?: string[];
  city_name?: string;
  country_name?: string;
  country_slug?: string;
  highlights: string[];
  body: string;
  faq: FaqItem[];
  variants: AudienceVariant[];
  draft_version?: number;
  model_c?: ModelCInfo | CityPicksResponse | CountryRollupInfo;
  page_type?: "city" | "country";
  top_cities?: TopCity[];
  top_regions?: TopRegion[];
  top_city_names?: string[];
  top_pick_titles?: string[];
  hero_image?: HeroImage | null;
}

export interface PublishedRecord {
  entity_id: string;
  entity_type: string;
  canonical_url: string;
  schema_json: Record<string, unknown>;
  content: PublishedContent;
  date_published: string;
  date_modified: string;
  version: number;
  status: string;
  index_state?: "indexed" | "noindex";
  content_locks?: Record<string, { locked?: boolean; edited_by?: string; locked_at?: string }>;
  content_candidates?: Record<string, { value: unknown; generated_at?: string }>;
}

export interface CityPick {
  slot: string;
  product_id: string;
  title: string;
  image_url?: string | null;
  price_from?: number | null;
  currency?: string | null;
  archetype: string;
  score: number;
  reason_codes: string[];
}

export interface DecisionProof {
  shortlist_reason: string;
  why_these_picks: string[];
  what_we_skipped: string[];
}

export interface CityPicksResponse {
  city_id: string;
  suppressed: boolean;
  reason: string | null;
  picks: CityPick[];
  decision_proof: DecisionProof;
}

export interface CountryRollupInfo {
  country: string;
  suppressed: boolean;
  reason: string | null;
  top_cities: Array<{ city_id: string; pick_count: number }>;
  top_products: CityPick[];
}

export interface PublishedListResponse {
  records: PublishedRecord[];
}

export interface TreeCity {
  entity_id: string;
  name: string;
  canonical_url: string;
}

export interface TreeCountry {
  entity_id: string;
  name: string;
  slug: string;
  canonical_url: string;
  cities: TreeCity[];
}

export interface DestinationsTreeResponse {
  countries: TreeCountry[];
}

export interface AdminOverview {
  destinations: number;
  products: number;
  published_records: number;
  drafts_validated: number;
  drafts_failed: number;
  pool_products: number;
  set_products: number;
}

export interface AdminCityRow {
  entity_id: string;
  name: string;
  country: string;
  region: string | null;
  published: boolean;
  products_count: number;
  attractions_count: number;
  picks_count: number;
  suppressed: boolean;
  source: string;
}

export interface AdminRegionRow {
  entity_id: string;
  name: string;
  country: string;
  published: boolean;
  source: string;
}

export interface AdminCountryRow {
  country: string;
  entity_id: string;
  published: boolean;
  index_state?: "indexed" | "noindex" | null;
  has_country_node: boolean;
  source: string;
  regions: AdminRegionRow[];
  cities: AdminCityRow[];
}

export interface AdminDestinationsResponse {
  countries: AdminCountryRow[];
}

export interface AdminProductRow {
  entity_id: string;
  name: string;
  city_id: string | null;
  city: string | null;
  country: string | null;
  category_group: string;
  image_url: string | null;
  price_from: number | null;
  currency: string | null;
  quality_score: number | null;
  completeness_score: number | null;
  in_pool: boolean;
  pool_reasons: string[];
  in_set: boolean;
  latest_severity: string | null;
  draft_status: string | null;
  draft_errors: string[];
  similarity: Record<string, unknown> | null;
  published: boolean;
  canonical_url: string | null;
  explain: ModelCInfo | null;
}

export interface AdminProductsResponse {
  products: AdminProductRow[];
}

export interface AdminContentRow {
  entity_id: string;
  name: string;
  latest_severity: string | null;
  draft_status: string | null;
  draft_version: number | null;
  validation_errors: string[];
  similarity: Record<string, unknown> | null;
  variant_count: number;
  published: boolean;
}

export interface AdminContentResponse {
  items: AdminContentRow[];
}

export interface AdminPublishingRow {
  entity_id: string;
  entity_type: string;
  name: string;
  status: string;
  index_state: "indexed" | "noindex";
  locked_fields: string[];
  canonical_url: string;
  date_modified: string;
  json_ld_nodes: number;
}

export interface AdminPublishingResponse {
  records: AdminPublishingRow[];
}

// --- Module 2: Destination Governance ---------------------------------

export interface AdminPendingDestinationRow {
  entity_id: string;
  name: string;
  country: string;
  region: string | null;
  city: string | null;
  destination_level: string;
  source: string;
  possible_duplicate_of: string | null;
}

export interface AdminPendingDestinationsResponse {
  pending: AdminPendingDestinationRow[];
}

export interface AdminSyncViatorCreatedRow {
  entity_id: string;
  name: string;
  country: string;
  destination_level: string;
  possible_duplicate_of: string | null;
}

export interface AdminSyncViatorResult {
  synced: number;
  skipped_existing: number;
  total_seen: number;
  created: AdminSyncViatorCreatedRow[];
}

export interface AdminDestinationActionResult {
  errors: string[];
  entity_id?: string;
  review_status?: string;
  canonical_entity_id?: string;
  products_reassigned?: number;
  attractions_reassigned?: number;
}

// --- Module 4: Product Ops Debugging Panel ------------------------------

export interface AdminProductDiffEntry {
  from_version: number;
  to_version: number;
  severity: string;
  changed_domains: string[];
  created_at: string;
}

export interface AdminProductLatestDraft {
  version: number;
  status: string;
  validation_errors: string[];
  similarity_band: string | null;
  similarity: Record<string, unknown> | null;
}

export interface AdminProductDebug {
  entity_id: string;
  diff_history: AdminProductDiffEntry[];
  latest_draft: AdminProductLatestDraft | null;
}

// --- Module 3: Canonical & Duplicate Inspector --------------------------

export interface AdminSimilarityRow {
  entity_id: string;
  version: number;
  band: string | null;
  score: number | null;
  nearest_entity_id: string | null;
}

export interface AdminSimilarityResponse {
  items: AdminSimilarityRow[];
}

// --- Module 8: Global Components Admin (Site Config) --------------------

export type AdminSiteConfigResponse = Record<string, unknown>;

// --- Module 10: Audit Log ------------------------------------------------

export interface AuditLogEntry {
  id: number;
  actor: string;
  action: string;
  entity_id: string;
  field: string | null;
  before_value: unknown;
  after_value: unknown;
  created_at: string;
}

export interface AuditLogResponse {
  entries: AuditLogEntry[];
}
