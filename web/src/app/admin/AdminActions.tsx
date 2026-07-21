"use client";

import { useState, useTransition } from "react";
import { BROWSER_API_BASE_URL } from "@/lib/api";
import type { AdminProductDebug } from "@/lib/types";

type Props = {
  endpoint: string;
  label: string;
  method?: "POST" | "GET";
  body?: Record<string, unknown>;
  compact?: boolean;
};

export function AdminAction({ endpoint, label, method = "POST", body, compact = false }: Props) {
  const [message, setMessage] = useState<string>("");
  const [isPending, startTransition] = useTransition();

  function run() {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await fetch(`${BROWSER_API_BASE_URL}${endpoint}`, {
          method,
          headers: { "Content-Type": "application/json" },
          body: body ? JSON.stringify(body) : undefined,
        });
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 120)}`);
          return;
        }
        setMessage("Done. Refresh to see updated data.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  return (
    <div className={compact ? "inline-flex flex-col gap-1" : "flex flex-col gap-1"}>
      <button
        type="button"
        onClick={run}
        disabled={isPending}
        className="rounded-md bg-brand-primary px-3 py-2 text-xs font-semibold text-white transition hover:bg-brand-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPending ? "Working..." : label}
      </button>
      {message && <span className="max-w-xs text-xs text-slate-500">{message}</span>}
    </div>
  );
}

type TaxonomyKind = "country" | "region" | "city" | "attraction";

function TaxonomyForm({ kind }: { kind: TaxonomyKind }) {
  const [country, setCountry] = useState("");
  const [region, setRegion] = useState("");
  const [city, setCity] = useState("");
  const [name, setName] = useState("");
  const [destinationEntityId, setDestinationEntityId] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  function submit() {
    const trimmedName = name.trim();
    const trimmedCountry = country.trim();
    if (!trimmedName || (kind !== "country" && kind !== "attraction" && !trimmedCountry)) {
      setMessage("Required fields are missing.");
      return;
    }
    if (kind === "attraction" && !destinationEntityId.trim() && !trimmedCountry) {
      setMessage("Use a city ID or provide country.");
      return;
    }
    setMessage("");
    startTransition(async () => {
      try {
        const payload =
          kind === "country"
            ? { name: trimmedName }
            : kind === "region"
              ? { country: trimmedCountry, name: trimmedName }
              : kind === "city"
                ? { country: trimmedCountry, region: region.trim() || undefined, name: trimmedName }
                : {
                    name: trimmedName,
                    destination_entity_id: destinationEntityId.trim() || undefined,
                    country: trimmedCountry || undefined,
                    city: city.trim() || undefined,
                  };
        const path =
          kind === "country"
            ? "/admin/countries"
            : kind === "city"
              ? "/admin/cities"
              : `/admin/${kind}s`;
        const response = await fetch(`${BROWSER_API_BASE_URL}${path}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 140)}`);
          return;
        }
        setName("");
        setCountry("");
        setRegion("");
        setCity("");
        setDestinationEntityId("");
        setMessage(`${kind[0].toUpperCase()}${kind.slice(1)} created. Refresh to see it.`);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  const label = kind[0].toUpperCase() + kind.slice(1);

  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <p className="text-sm font-semibold text-brand-navy">{label}</p>
      <div className="mt-3 grid gap-2">
        {kind !== "country" && (
          <input
            value={country}
            onChange={(event) => setCountry(event.target.value)}
            placeholder={kind === "attraction" ? "Country fallback" : "Country"}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-primary"
          />
        )}
        {kind === "city" && (
          <input
            value={region}
            onChange={(event) => setRegion(event.target.value)}
            placeholder="Region optional"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-primary"
          />
        )}
        {kind === "attraction" && (
          <>
            <input
              value={destinationEntityId}
              onChange={(event) => setDestinationEntityId(event.target.value)}
              placeholder="City entity ID optional"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-primary"
            />
            <input
              value={city}
              onChange={(event) => setCity(event.target.value)}
              placeholder="City fallback"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-primary"
            />
          </>
        )}
        <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
          Name
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={label}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-brand-navy outline-none focus:border-brand-primary"
          />
        </label>
        <button
          type="button"
          onClick={submit}
          disabled={isPending}
          className="rounded-md bg-brand-primary px-3 py-2 text-xs font-semibold text-white transition hover:bg-brand-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "Creating..." : `Create ${kind}`}
        </button>
      </div>
      {message && <p className="mt-2 text-xs text-slate-500">{message}</p>}
    </div>
  );
}

export function TaxonomyCreatePanel() {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
      <div className="mb-3">
        <h3 className="font-semibold text-brand-navy">Taxonomy fallback creation</h3>
        <p className="mt-1 text-xs text-slate-600">
          Use only when imported destination data is missing a required node.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TaxonomyForm kind="country" />
        <TaxonomyForm kind="region" />
        <TaxonomyForm kind="city" />
        <TaxonomyForm kind="attraction" />
      </div>
    </div>
  );
}

export function SyncViatorForm() {
  const [country, setCountry] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  function submit() {
    setMessage("");
    startTransition(async () => {
      try {
        const query = country.trim() ? `?country=${encodeURIComponent(country.trim())}` : "";
        const response = await fetch(`${BROWSER_API_BASE_URL}/admin/destinations/sync-viator${query}`, {
          method: "POST",
        });
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 140)}`);
          return;
        }
        const data = (await response.json()) as {
          synced: number;
          skipped_existing: number;
          total_seen: number;
        };
        setMessage(
          `Synced ${data.synced} new, skipped ${data.skipped_existing} existing, ${data.total_seen} total seen. Refresh to see the pending queue.`,
        );
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
        Country (optional)
        <input
          value={country}
          onChange={(event) => setCountry(event.target.value)}
          placeholder="e.g. Italy"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-normal text-brand-navy outline-none focus:border-brand-primary"
        />
      </label>
      <button
        type="button"
        onClick={submit}
        disabled={isPending}
        className="rounded-md bg-brand-primary px-3 py-2 text-xs font-semibold text-white transition hover:bg-brand-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPending ? "Syncing..." : "Sync from Viator"}
      </button>
      {message && <span className="max-w-md text-xs text-slate-500">{message}</span>}
    </div>
  );
}

export function MergeDestinationForm({
  entityId,
  defaultCanonicalId,
}: {
  entityId: string;
  defaultCanonicalId: string;
}) {
  const [canonicalId, setCanonicalId] = useState(defaultCanonicalId);
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  function submit() {
    const trimmed = canonicalId.trim();
    if (!trimmed) {
      setMessage("Canonical entity ID is required.");
      return;
    }
    setMessage("");
    startTransition(async () => {
      try {
        const response = await fetch(
          `${BROWSER_API_BASE_URL}/admin/destinations/${encodeURIComponent(entityId)}/merge`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ canonical_entity_id: trimmed }),
          },
        );
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 140)}`);
          return;
        }
        setMessage("Merged. Refresh to see updated data.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
        Merge into canonical entity ID
        <input
          value={canonicalId}
          onChange={(event) => setCanonicalId(event.target.value)}
          placeholder="canonical entity_id"
          className="w-56 rounded-md border border-slate-300 px-3 py-2 text-sm font-normal text-brand-navy outline-none focus:border-brand-primary"
        />
      </label>
      <button
        type="button"
        onClick={submit}
        disabled={isPending}
        className="rounded-md border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPending ? "Merging..." : "Merge"}
      </button>
      {message && <span className="max-w-xs text-xs text-slate-500">{message}</span>}
    </div>
  );
}

function formatFieldValue(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

// Structural/non-editorial fields present on every entity type's published
// content that should never show up as an editable field, even though
// they're technically strings (or the h1/meta fields are always relevant).
const NON_EDITORIAL_FIELDS = new Set([
  "canonical_url",
  "country_name",
  "country_slug",
  "city_name",
  "page_type",
  "draft_version",
  "hero_image",
]);
// Always offered even if a specific record's content doesn't have every one
// yet (e.g. a brand-new record before its first draft).
const ALWAYS_OFFERED_FIELDS = ["h1", "meta_title", "meta_description", "overview", "body"];

function editableFieldOptions(liveContent?: Record<string, unknown>): string[] {
  if (!liveContent) return ALWAYS_OFFERED_FIELDS;
  const fromContent = Object.keys(liveContent).filter((key) => !NON_EDITORIAL_FIELDS.has(key));
  const merged = new Set([...ALWAYS_OFFERED_FIELDS, ...fromContent]);
  return Array.from(merged);
}

function fieldLabel(field: string): string {
  return field
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function ContentLockForm({
  entityId,
  lockedFields,
  liveContent,
  candidates,
}: {
  entityId: string;
  lockedFields: string[];
  liveContent?: Record<string, unknown>;
  candidates?: Record<string, { value: unknown; generated_at?: string }>;
}) {
  const [field, setField] = useState("h1");
  const [value, setValue] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();
  const isLocked = lockedFields.includes(field);
  const candidate = candidates?.[field];
  const liveValue = liveContent?.[field];

  function post(path: string, body?: Record<string, unknown>) {
    return fetch(`${BROWSER_API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  function parsedFieldValue(raw: string): unknown {
    // highlights/facts/faq/etc are arrays or objects on the live record -
    // accept JSON for those (paste e.g. ["tip one","tip two"]), and fall
    // back to the raw string for plain text fields like h1/overview.
    const trimmed = raw.trim();
    try {
      return JSON.parse(trimmed);
    } catch {
      return trimmed;
    }
  }

  function submit(unlock = false) {
    if (!unlock && !value.trim()) {
      setMessage("Content value is required.");
      return;
    }
    setMessage("");
    startTransition(async () => {
      try {
        const response = await post(`/published/${entityId}/content`,
          unlock
            ? { unlock_fields: [field], edited_by: "admin_ui" }
            : { updates: { [field]: parsedFieldValue(value) }, edited_by: "admin_ui" },
        );
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 140)}`);
          return;
        }
        setValue("");
        setMessage(unlock ? "Unlocked. Refresh to see updated data." : "Saved and locked. Refresh to see updated data.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  function regenerate() {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await post(`/published/${entityId}/regenerate`, { field });
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 140)}`);
          return;
        }
        setMessage("Regenerated as candidate. Refresh to review it below.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  function resolveCandidate(action: "accept" | "reject") {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await post(`/published/${entityId}/candidates/${field}/${action}`);
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 140)}`);
          return;
        }
        setMessage(
          action === "accept"
            ? "Candidate accepted as the live value. Refresh to see it."
            : "Candidate rejected. Refresh to confirm.",
        );
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  function revert() {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await post(`/published/${entityId}/revert`, { field });
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 140)}`);
          return;
        }
        setMessage("Reverted to latest AI version and cleared the lock. Refresh to see it.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  return (
    <div className="mt-3 rounded-md border border-slate-200 bg-white p-3">
      <div className="grid gap-2">
        <select
          value={field}
          onChange={(event) => setField(event.target.value)}
          className="rounded-md border border-slate-300 px-2 py-2 text-xs text-brand-navy outline-none focus:border-brand-primary"
        >
          {editableFieldOptions(liveContent).map((option) => (
            <option key={option} value={option}>
              {fieldLabel(option)}
            </option>
          ))}
        </select>
        {liveValue !== undefined && (
          <p className="truncate rounded-md bg-slate-50 px-2 py-1 text-xs text-slate-500">
            Live: {formatFieldValue(liveValue).slice(0, 160)}
          </p>
        )}
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={
            typeof liveValue === "string" || liveValue === undefined
              ? `New ${fieldLabel(field).toLowerCase()}`
              : `New ${fieldLabel(field).toLowerCase()} - paste JSON, e.g. ["item one","item two"]`
          }
          rows={typeof liveValue === "string" || liveValue === undefined ? 2 : 4}
          className="rounded-md border border-slate-300 px-2 py-2 text-xs text-brand-navy outline-none focus:border-brand-primary"
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => submit(false)}
            disabled={isPending}
            className="rounded-md bg-brand-primary px-3 py-2 text-xs font-semibold text-white transition hover:bg-brand-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? "Saving..." : "Save + lock"}
          </button>
          {isLocked && (
            <button
              type="button"
              onClick={() => submit(true)}
              disabled={isPending}
              className="rounded-md border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Unlock
            </button>
          )}
          {isLocked && (
            <button
              type="button"
              onClick={revert}
              disabled={isPending}
              className="rounded-md border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Revert to latest AI version
            </button>
          )}
          <button
            type="button"
            onClick={regenerate}
            disabled={isPending}
            className="rounded-md border border-brand-primary px-3 py-2 text-xs font-semibold text-brand-primary transition hover:bg-brand-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Regenerate as candidate
          </button>
        </div>
        {candidate && (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-2">
            <p className="text-xs font-semibold text-amber-800">Pending candidate</p>
            <p className="mt-1 truncate text-xs text-amber-700">
              {formatFieldValue(candidate.value).slice(0, 200)}
            </p>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() => resolveCandidate("accept")}
                disabled={isPending}
                className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-brand-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
              >
                Accept
              </button>
              <button
                type="button"
                onClick={() => resolveCandidate("reject")}
                disabled={isPending}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Reject
              </button>
            </div>
          </div>
        )}
      </div>
      {message && <p className="mt-2 text-xs text-slate-500">{message}</p>}
    </div>
  );
}

export type HeroImageValue = {
  url: string;
  alt_text: string;
  source_class: string;
  rights_status: string;
  indexable: boolean;
  generator: string;
  generated_at: string;
};

function GeneratorBadge({ generator }: { generator: string }) {
  const isAi = generator === "nano_banana_pro";
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
        isAi ? "bg-violet-50 text-violet-700" : "bg-sky-50 text-sky-700"
      }`}
    >
      {isAi ? "AI generated" : "Uploaded"}
    </span>
  );
}

function HeroImagePreview({ image }: { image: HeroImageValue }) {
  return (
    <div className="mt-2">
      <div className="flex items-center gap-2">
        <GeneratorBadge generator={image.generator} />
        <span className="text-xs text-slate-500">
          source_class {image.source_class} - indexable {String(image.indexable)}
        </span>
      </div>
      <img
        src={`${BROWSER_API_BASE_URL}${image.url}`}
        alt={image.alt_text}
        className="mt-2 h-32 w-full rounded-md object-cover"
      />
    </div>
  );
}

function HeroImageUploadControl({
  entityId,
  buttonLabel,
  onDone,
}: {
  entityId: string;
  buttonLabel: string;
  onDone: (message: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [isPending, startTransition] = useTransition();

  function upload() {
    if (!file) {
      onDone("Choose an image file first.");
      return;
    }
    startTransition(async () => {
      try {
        const formData = new FormData();
        formData.append("file", file);
        const response = await fetch(`${BROWSER_API_BASE_URL}/published/${entityId}/hero-image/upload`, {
          method: "POST",
          body: formData,
        });
        if (!response.ok) {
          const text = await response.text();
          onDone(`Failed ${response.status}: ${text.slice(0, 200)}`);
          return;
        }
        setFile(null);
        onDone("Uploaded and locked as the live hero image.");
      } catch (error) {
        onDone(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        className="text-xs text-slate-600"
      />
      <button
        type="button"
        onClick={upload}
        disabled={isPending}
        className="rounded-md border border-sky-600 px-3 py-2 text-xs font-semibold text-sky-700 transition hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPending ? "Uploading..." : buttonLabel}
      </button>
    </div>
  );
}

export function HeroImageForm({
  entityId,
  entityType,
  liveHeroImage,
  candidate,
}: {
  entityId: string;
  entityType: "country" | "city";
  liveHeroImage?: HeroImageValue | null;
  candidate?: { value: unknown; generated_at?: string };
}) {
  const [message, setMessage] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [isPending, startTransition] = useTransition();

  function post(path: string) {
    return fetch(`${BROWSER_API_BASE_URL}${path}`, { method: "POST" });
  }

  function generate() {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await post(`/published/${entityId}/hero-image/regenerate`);
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 200)}`);
          return;
        }
        setMessage("Generated. Review the candidate below, then Accept or Reject.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  function resolveCandidate(action: "accept" | "reject") {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await post(`/published/${entityId}/candidates/hero_image/${action}`);
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 200)}`);
          return;
        }
        setMessage(action === "accept" ? "Hero image accepted as live." : "Candidate rejected.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  const candidateImage = candidate?.value as HeroImageValue | undefined;

  return (
    <div className="mt-3 rounded-md border border-slate-200 bg-white p-3">
      <p className="text-xs font-semibold text-brand-navy">
        {entityType === "country"
          ? "Hero image - AI-generated (Nano Banana Pro)"
          : "Hero image - uploaded photo (CMS media)"}
      </p>
      <p className="text-[11px] text-slate-400">
        {entityType === "country"
          ? "WBS: no curated image exists for countries, so this is generated."
          : "WBS: city hero images come from real CMS media, never AI-generated."}
      </p>

      {liveHeroImage ? (
        <HeroImagePreview image={liveHeroImage} />
      ) : (
        <p className="mt-2 text-xs text-slate-500">No hero image set yet.</p>
      )}

      {entityType === "country" ? (
        <>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={generate}
              disabled={isPending}
              className="rounded-md border border-brand-primary px-3 py-2 text-xs font-semibold text-brand-primary transition hover:bg-brand-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isPending ? "Working..." : liveHeroImage ? "Regenerate hero image" : "Generate hero image"}
            </button>
            <button
              type="button"
              onClick={() => setShowUpload((prev) => !prev)}
              className="text-xs text-slate-500 underline decoration-dotted hover:text-slate-700"
            >
              {showUpload ? "Cancel manual override" : "Or upload a photo instead"}
            </button>
          </div>
          {showUpload && (
            <div className="mt-2">
              <HeroImageUploadControl entityId={entityId} buttonLabel="Upload override" onDone={setMessage} />
            </div>
          )}
          {candidateImage && (
            <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-2">
              <p className="text-xs font-semibold text-amber-800">Pending candidate</p>
              <img
                src={`${BROWSER_API_BASE_URL}${candidateImage.url}`}
                alt={candidateImage.alt_text}
                className="mt-2 h-32 w-full rounded-md object-cover"
              />
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => resolveCandidate("accept")}
                  disabled={isPending}
                  className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-brand-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Accept
                </button>
                <button
                  type="button"
                  onClick={() => resolveCandidate("reject")}
                  disabled={isPending}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Reject
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="mt-3">
          <HeroImageUploadControl
            entityId={entityId}
            buttonLabel={liveHeroImage ? "Replace hero image" : "Upload hero image"}
            onDone={setMessage}
          />
        </div>
      )}
      {message && <p className="mt-2 text-xs text-slate-500">{message}</p>}
    </div>
  );
}

export type BatchPage = { entity_id: string; page_type: "product"; name: string };

export type PendingBatch = {
  pages: BatchPage[];
  sampled_entity_ids: string[];
  status: string;
  created_at: string;
};

type PagePreview = {
  h1?: string;
  meta_title?: string;
  meta_description?: string;
  overview?: string;
  body?: string;
  highlights?: string[];
  faq?: { question: string; answer: string }[];
};

function SampledPageReview({ page }: { page: BatchPage }) {
  const [preview, setPreview] = useState<PagePreview | null>(null);
  const [usedFallback, setUsedFallback] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const draftResponse = await fetch(`${BROWSER_API_BASE_URL}/entities/${page.entity_id}/content`);
      if (draftResponse.ok) {
        setPreview((await draftResponse.json()) as PagePreview);
        return;
      }
      // No new draft ready for this product yet (no MAJOR diff pending, per
      // the Diff Engine's hard rule) - fall back to what's currently live,
      // since that's what Pass would leave unchanged for this page anyway.
      const liveResponse = await fetch(`${BROWSER_API_BASE_URL}/published/${page.entity_id}`);
      if (liveResponse.ok) {
        const record = (await liveResponse.json()) as { content: PagePreview };
        setPreview(record.content);
        setUsedFallback(true);
        return;
      }
      // No draft and no individual publish record for this product - it has
      // nothing to preview, and Pass will simply leave it untouched (it's
      // only referenced today via the city's Model C picks).
      setError(
        "No content to preview - this page has no AI draft and isn't individually published yet. " +
          "Pass will leave it unchanged.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-2 rounded-md border border-amber-100 bg-white p-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-slate-600">
          {page.name} <span className="text-slate-400">({page.page_type})</span>
        </p>
        {!preview && (
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="rounded border border-slate-300 px-2 py-1 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
          >
            {loading ? "Loading..." : "View proposed content"}
          </button>
        )}
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      {preview && usedFallback && (
        <p className="mt-1 text-[11px] text-slate-400">
          No new AI draft pending for this page (no MAJOR change detected) - showing current live
          content, which is what Pass would leave unchanged.
        </p>
      )}
      {preview && (
        <div className="mt-2 space-y-1 text-xs text-slate-600">
          {preview.h1 && (
            <p>
              <span className="font-medium text-slate-500">H1:</span> {preview.h1}
            </p>
          )}
          {preview.meta_title && (
            <p>
              <span className="font-medium text-slate-500">Meta title:</span> {preview.meta_title}
            </p>
          )}
          {(preview.overview || preview.body) && (
            <p>
              <span className="font-medium text-slate-500">Body:</span>{" "}
              {(preview.overview || preview.body || "").slice(0, 220)}
            </p>
          )}
          {preview.faq && preview.faq.length > 0 && (
            <p>
              <span className="font-medium text-slate-500">FAQ:</span> {preview.faq.length} questions - e.g. &quot;
              {preview.faq[0].question}&quot;
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function QaBatchForm({
  entityId,
  pendingBatch: initialPendingBatch,
}: {
  entityId: string;
  liveContent?: Record<string, unknown>;
  pendingBatch?: PendingBatch | null;
}) {
  const [pendingBatch, setPendingBatch] = useState<PendingBatch | null | undefined>(initialPendingBatch);
  const [notes, setNotes] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  function post(path: string, body?: Record<string, unknown>) {
    return fetch(`${BROWSER_API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  function runBatch() {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await post(`/cities/${entityId}/batch/run`);
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 200)}`);
          return;
        }
        const data = (await response.json()) as { pending_batch: PendingBatch | null };
        setPendingBatch(data.pending_batch);
        setMessage(
          data.pending_batch
            ? `Batch run: ${data.pending_batch.pages.length} page(s) in this batch, ${data.pending_batch.sampled_entity_ids.length} sampled for review below.`
            : "Batch run, but no sample was returned - try again.",
        );
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  function review(decision: "pass" | "fail") {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await post(`/cities/${entityId}/batch/review`, {
          decision,
          notes: notes.trim() || undefined,
        });
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 200)}`);
          return;
        }
        setNotes("");
        setPendingBatch(null);
        setMessage(
          decision === "pass"
            ? "Sample passed - every product page in the batch is now live. Refresh to see updates above."
            : "Sample failed - batch discarded, nothing published.",
        );
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  return (
    <div className="mt-3 rounded-md border border-slate-200 bg-white p-3">
      <p className="text-xs font-semibold text-brand-navy">Run AI Batch (Human QA Sampling)</p>
      <p className="mt-1 text-[11px] text-slate-400">
        SOW 2.11 / Pipeline View batch model: a batch is every product page linked to this city
        (the city page itself has its own separate lock/edit governance below). 3-5% of the
        product pages are sampled for manual review; pass/fail applies to the whole batch
        together.
      </p>
      {!pendingBatch ? (
        <button
          type="button"
          onClick={runBatch}
          disabled={isPending}
          className="mt-3 rounded-md border border-brand-primary px-3 py-2 text-xs font-semibold text-brand-primary transition hover:bg-brand-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "Running..." : "Run AI Batch"}
        </button>
      ) : (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-semibold text-amber-800">
            Batch: {pendingBatch.pages.length} product page(s) - {pendingBatch.sampled_entity_ids.length}{" "}
            sampled for QA review
          </p>
          {pendingBatch.pages
            .filter((page) => pendingBatch.sampled_entity_ids.includes(page.entity_id))
            .map((page) => (
              <SampledPageReview key={page.entity_id} page={page} />
            ))}
          <p className="mt-2 text-[11px] text-slate-500">
            Not sampled ({pendingBatch.pages.length - pendingBatch.sampled_entity_ids.length}):{" "}
            {pendingBatch.pages
              .filter((page) => !pendingBatch.sampled_entity_ids.includes(page.entity_id))
              .map((page) => page.name)
              .join(", ") || "none"}
          </p>
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Notes (optional, useful on fail)"
            rows={2}
            className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-brand-navy outline-none focus:border-brand-primary"
          />
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => review("pass")}
              disabled={isPending}
              className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-brand-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
            >
              Pass - publish full batch
            </button>
            <button
              type="button"
              onClick={() => review("fail")}
              disabled={isPending}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Fail - discard batch
            </button>
          </div>
        </div>
      )}
      {message && <p className="mt-2 text-xs text-slate-500">{message}</p>}
    </div>
  );
}

export function ProductDebugPanel({ entityId }: { entityId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [debugData, setDebugData] = useState<AdminProductDebug | null>(null);
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  function toggle() {
    if (expanded) {
      setExpanded(false);
      return;
    }
    setExpanded(true);
    if (debugData) return;
    setMessage("");
    startTransition(async () => {
      try {
        const response = await fetch(
          `${BROWSER_API_BASE_URL}/admin/products/${encodeURIComponent(entityId)}/debug`,
        );
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 140)}`);
          return;
        }
        setDebugData((await response.json()) as AdminProductDebug);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  return (
    <div>
      <button
        type="button"
        onClick={toggle}
        disabled={isPending}
        className="rounded-md border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPending ? "Loading..." : expanded ? "Hide debug" : "Debug"}
      </button>
      {expanded && (
        <div className="mt-2 max-w-md rounded-md border border-slate-200 bg-slate-50 p-3">
          {message && <p className="text-xs text-red-600">{message}</p>}
          {debugData && (
            <>
              <p className="text-xs font-semibold text-brand-navy">Diff history</p>
              {debugData.diff_history.length === 0 && (
                <p className="text-xs text-slate-500">No diff history recorded.</p>
              )}
              <ul className="mt-1 space-y-1">
                {debugData.diff_history.map((diff, index) => (
                  <li key={`${diff.from_version}-${diff.to_version}-${index}`} className="text-xs text-slate-600">
                    v{diff.from_version} to v{diff.to_version} - {diff.severity} - {diff.changed_domains.join(", ") || "no domains"} -{" "}
                    {diff.created_at}
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs font-semibold text-brand-navy">Latest draft</p>
              {debugData.latest_draft ? (
                <div className="mt-1 text-xs text-slate-600">
                  <p>
                    version {debugData.latest_draft.version} - status {debugData.latest_draft.status} - similarity band{" "}
                    {debugData.latest_draft.similarity_band ?? "n/a"}
                  </p>
                  {debugData.latest_draft.validation_errors.length > 0 && (
                    <p className="mt-1 text-red-600">
                      {debugData.latest_draft.validation_errors.join(", ")}
                    </p>
                  )}
                </div>
              ) : (
                <p className="mt-1 text-xs text-slate-500">No draft recorded.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function SiteConfigForm({
  configKey,
  initialValue,
}: {
  configKey: string;
  initialValue: unknown;
}) {
  const [text, setText] = useState(JSON.stringify(initialValue, null, 2));
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  function submit() {
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      setMessage("Value must be valid JSON.");
      return;
    }
    setMessage("");
    startTransition(async () => {
      try {
        const response = await fetch(
          `${BROWSER_API_BASE_URL}/admin/site-config/${encodeURIComponent(configKey)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(parsed),
          },
        );
        if (!response.ok) {
          const errText = await response.text();
          setMessage(`Failed ${response.status}: ${errText.slice(0, 140)}`);
          return;
        }
        setMessage("Saved. Refresh to confirm.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <p className="text-sm font-semibold text-brand-navy">{configKey}</p>
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={6}
        className="mt-2 w-full rounded-md border border-slate-300 px-2 py-2 font-mono text-xs text-brand-navy outline-none focus:border-brand-primary"
      />
      <button
        type="button"
        onClick={submit}
        disabled={isPending}
        className="mt-2 rounded-md bg-brand-primary px-3 py-2 text-xs font-semibold text-white transition hover:bg-brand-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPending ? "Saving..." : "Save"}
      </button>
      {message && <p className="mt-2 text-xs text-slate-500">{message}</p>}
    </div>
  );
}
