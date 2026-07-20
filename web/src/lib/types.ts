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
  published: boolean;
  products_count: number;
  picks_count: number;
  suppressed: boolean;
}

export interface AdminCountryRow {
  country: string;
  entity_id: string;
  published: boolean;
  has_country_node: boolean;
  source: string;
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
  canonical_url: string;
  date_modified: string;
  json_ld_nodes: number;
}

export interface AdminPublishingResponse {
  records: AdminPublishingRow[];
}
