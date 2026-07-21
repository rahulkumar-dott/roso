"use client";

import { useMemo, useState } from "react";
import type { AdminPublishingRow } from "@/lib/types";
import { ContentLockForm, HeroImageForm, type HeroImageValue } from "./AdminActions";
import { StatusBadge } from "./shared";

export type ContentBrowserRow = AdminPublishingRow & { countrySlug: string | null };

function RecordEditor({
  row,
  liveContent,
  candidates,
}: {
  row: ContentBrowserRow;
  liveContent?: Record<string, unknown>;
  candidates?: Record<string, { value: unknown; generated_at?: string }>;
}) {
  return (
    <div className="rounded-md bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-brand-navy">{row.name}</p>
          <p className="text-xs text-slate-500">
            {row.entity_type} - {row.index_state} - JSON-LD nodes {row.json_ld_nodes}
          </p>
          {row.locked_fields.length > 0 && (
            <p className="mt-1 text-xs text-emerald-700">Locked: {row.locked_fields.join(", ")}</p>
          )}
          <a href={row.canonical_url} className="mt-1 block truncate text-xs text-brand-primary">
            {row.canonical_url}
          </a>
        </div>
        <StatusBadge active={row.status === "published"} label={row.status} />
      </div>
      {(row.entity_type === "country" || row.entity_type === "city") && (
        <HeroImageForm
          entityId={row.entity_id}
          entityType={row.entity_type}
          liveHeroImage={liveContent?.hero_image as HeroImageValue | null | undefined}
          candidate={candidates?.hero_image}
        />
      )}
      <ContentLockForm
        entityId={row.entity_id}
        lockedFields={row.locked_fields}
        liveContent={liveContent}
        candidates={candidates}
      />
    </div>
  );
}

export function ContentCountryBrowser({
  rows,
  liveContentByEntity,
  candidatesByEntity,
}: {
  rows: ContentBrowserRow[];
  liveContentByEntity: Record<string, Record<string, unknown>>;
  candidatesByEntity: Record<string, Record<string, { value: unknown; generated_at?: string }>>;
}) {
  const countries = useMemo(
    () =>
      rows
        .filter((row) => row.entity_type === "country")
        .sort((a, b) => a.name.localeCompare(b.name)),
    [rows],
  );
  const [filter, setFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedCityId, setSelectedCityId] = useState<string | null>(null);

  const visibleCountries = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) return countries;
    return countries.filter((country) => country.name.toLowerCase().includes(query));
  }, [countries, filter]);

  const selectedCountry = countries.find((country) => country.entity_id === selectedId) ?? null;

  const children = useMemo(() => {
    if (!selectedCountry) return [];
    return rows.filter(
      (row) => row.entity_type !== "country" && row.countrySlug === selectedCountry.countrySlug,
    );
  }, [rows, selectedCountry]);

  return (
    <div className="grid gap-4 md:grid-cols-[220px_1fr]">
      <div className="rounded-md border border-slate-200 bg-white p-2">
        <input
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filter countries"
          className="mb-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-brand-navy outline-none focus:border-brand-primary"
        />
        <div className="flex max-h-[520px] flex-col gap-1 overflow-y-auto">
          {visibleCountries.map((country) => (
            <button
              key={country.entity_id}
              type="button"
              onClick={() => {
                setSelectedId(country.entity_id);
                setSelectedCityId(null);
              }}
              className={`rounded-md px-2 py-2 text-left text-xs font-medium transition ${
                country.entity_id === selectedId
                  ? "bg-brand-primary text-white"
                  : "text-brand-navy hover:bg-slate-100"
              }`}
            >
              {country.name}
              <span className={country.entity_id === selectedId ? "ml-1 opacity-80" : "ml-1 text-slate-400"}>
                ({rows.filter((r) => r.entity_type !== "country" && r.countrySlug === country.countrySlug).length})
              </span>
            </button>
          ))}
          {visibleCountries.length === 0 && (
            <p className="px-2 py-2 text-xs text-slate-500">No countries match.</p>
          )}
        </div>
      </div>

      <div className="space-y-3">
        {!selectedCountry && (
          <p className="rounded-md border border-dashed border-slate-300 p-4 text-xs text-slate-500">
            Select a country on the left to see its editable content and its cities.
          </p>
        )}
        {selectedCountry && (
          <>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Country page
              </p>
              <RecordEditor
                row={selectedCountry}
                liveContent={liveContentByEntity[selectedCountry.entity_id]}
                candidates={candidatesByEntity[selectedCountry.entity_id]}
              />
            </div>

            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Cities in {selectedCountry.name} - pick one to edit
              </p>
              {children.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {children.map((row) => (
                    <button
                      key={row.entity_id}
                      type="button"
                      onClick={() =>
                        setSelectedCityId((current) => (current === row.entity_id ? null : row.entity_id))
                      }
                      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                        row.entity_id === selectedCityId
                          ? "border-brand-primary bg-brand-primary text-white"
                          : "border-slate-200 bg-white text-brand-navy hover:bg-slate-100"
                      }`}
                    >
                      {row.name}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">No published cities under this country yet.</p>
              )}
            </div>

            {selectedCityId &&
              (() => {
                const cityRow = children.find((row) => row.entity_id === selectedCityId);
                if (!cityRow) return null;
                return (
                  <RecordEditor
                    row={cityRow}
                    liveContent={liveContentByEntity[cityRow.entity_id]}
                    candidates={candidatesByEntity[cityRow.entity_id]}
                  />
                );
              })()}
          </>
        )}
      </div>
    </div>
  );
}
