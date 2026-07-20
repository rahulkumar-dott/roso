"use client";

import { useState, useTransition } from "react";
import { BROWSER_API_BASE_URL } from "@/lib/api";

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
