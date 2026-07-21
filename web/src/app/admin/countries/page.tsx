import Link from "next/link";
import { getAdminPendingDestinations, getAdminPublishing, getDestinationsTree } from "@/lib/api";
import { StatusBadge } from "../shared";

export default async function AdminCountriesPage() {
  const [tree, publishing, pending] = await Promise.all([
    getDestinationsTree(),
    getAdminPublishing(),
    getAdminPendingDestinations(),
  ]);

  const publishedByEntity = new Map((publishing?.records ?? []).map((row) => [row.entity_id, row]));
  const pendingCountryIds = new Set(
    (pending?.pending ?? [])
      .filter((row) => row.destination_level === "COUNTRY")
      .map((row) => row.entity_id),
  );

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-xl font-semibold text-brand-navy">Countries</h2>
      <p className="mt-1 text-sm text-slate-600">
        One screen per country: approve/reject/merge (if pending), publish, promote, hero image,
        content editing, and governance status - everything in one place.
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {tree?.countries.map((country) => {
          const row = publishedByEntity.get(country.entity_id);
          const isPending = pendingCountryIds.has(country.entity_id);
          return (
            <Link
              key={country.entity_id}
              href={`/admin/countries/${country.slug}`}
              className="rounded-lg border border-slate-200 bg-slate-50 p-4 transition hover:border-brand-primary hover:bg-white"
            >
              <p className="font-medium text-brand-navy">{country.name}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {row ? (
                  <StatusBadge
                    active={row.index_state === "indexed"}
                    label={row.index_state === "indexed" ? "Indexed" : "Noindex"}
                  />
                ) : (
                  <StatusBadge active={false} label="Not published" />
                )}
                {isPending && <StatusBadge active={false} label="Pending review" />}
              </div>
              <p className="mt-2 text-xs text-slate-500">{country.cities.length} cities</p>
            </Link>
          );
        })}
        {(!tree || tree.countries.length === 0) && (
          <p className="text-xs text-slate-500">No countries found.</p>
        )}
      </div>
    </section>
  );
}
