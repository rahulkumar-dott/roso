import Link from "next/link";
import { getAdminDestinations, getAdminPendingDestinations } from "@/lib/api";
import { AdminAction, MergeDestinationForm, SyncViatorForm, TaxonomyCreatePanel } from "../AdminActions";
import { StatusBadge } from "../shared";

export default async function AdminDestinationsPage() {
  const [destinations, pendingDestinations] = await Promise.all([
    getAdminDestinations(),
    getAdminPendingDestinations(),
  ]);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-xl font-semibold text-brand-navy">Destinations</h2>
      <p className="mt-1 text-sm text-slate-600">
        Taxonomy management for the geographic hierarchy used by breadcrumbs, SEO state, city
        hubs, country pages, and attraction mapping.
      </p>
      <div className="mt-4">
        <TaxonomyCreatePanel />
      </div>

      <div className="mt-6 rounded-md border border-slate-200 bg-slate-50 p-4">
        <div className="mb-3">
          <h3 className="font-semibold text-brand-navy">Destination governance (Viator sync)</h3>
          <p className="mt-1 text-xs text-slate-600">
            Destinations are ingested from Viator as pending review, not immediately live.
            Approve, reject, or merge duplicates below; a destination only becomes active once
            approved and linked to at least one product.
          </p>
        </div>
        <SyncViatorForm />
        <div className="mt-4 space-y-3">
          {pendingDestinations && pendingDestinations.pending.length > 0 ? (
            pendingDestinations.pending.map((row) => (
              <div key={row.entity_id} className="rounded-md border border-slate-200 bg-white p-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-brand-navy">{row.name}</p>
                    <p className="text-xs text-slate-500">
                      {row.country} - {row.destination_level} - {row.entity_id}
                    </p>
                    {row.possible_duplicate_of && (
                      <span className="mt-1 inline-block rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                        Possible duplicate of {row.possible_duplicate_of}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <AdminAction
                      endpoint={`/admin/destinations/${row.entity_id}/approve`}
                      label="Approve"
                      compact
                    />
                    <AdminAction
                      endpoint={`/admin/destinations/${row.entity_id}/reject`}
                      label="Reject"
                      compact
                    />
                  </div>
                </div>
                <div className="mt-3">
                  <MergeDestinationForm
                    entityId={row.entity_id}
                    defaultCanonicalId={row.possible_duplicate_of ?? ""}
                  />
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs text-slate-500">No destinations pending review.</p>
          )}
        </div>
      </div>

      <div className="mt-5 space-y-5">
        {destinations?.countries.map((country) => (
          <div key={country.entity_id} className="rounded-lg border border-slate-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold text-brand-navy">{country.country}</h3>
                <div className="mt-1 flex flex-wrap gap-2">
                  <StatusBadge active={country.published} label={country.published ? "Published" : "Not published"} />
                  <StatusBadge
                    active={country.has_country_node}
                    label={country.has_country_node ? `${country.source} taxonomy` : "Grouped from cities"}
                  />
                  {country.index_state && (
                    <StatusBadge active={country.index_state === "indexed"} label={country.index_state} />
                  )}
                  <span className="text-xs text-slate-500">{country.cities.length} cities</span>
                  <span className="text-xs text-slate-500">{country.regions.length} regions</span>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <AdminAction
                  endpoint={`/countries/${encodeURIComponent(country.country)}/publish`}
                  label="Publish country page"
                  compact
                />
                {country.published && country.index_state !== "indexed" && (
                  <AdminAction
                    endpoint={`/countries/${encodeURIComponent(country.country)}/promote`}
                    label="Promote to indexed"
                    compact
                  />
                )}
              </div>
            </div>
            {country.regions.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {country.regions.map((region) => (
                  <span
                    key={region.entity_id}
                    className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600"
                  >
                    {region.name} · {region.source}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              {country.cities.map((city) => (
                <div key={city.entity_id} className="rounded-md bg-slate-50 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-brand-navy">{city.name}</p>
                      <p className="text-xs text-slate-500">
                        {city.region ? `${city.region} · ` : ""}
                        {city.products_count} products, {city.attractions_count} attractions,{" "}
                        {city.picks_count} picks
                      </p>
                    </div>
                    <StatusBadge active={city.published} label={city.published ? "Live" : "Draft"} />
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Link href={`/city/${city.entity_id}`} className="text-xs font-medium text-brand-primary">
                      View
                    </Link>
                    <AdminAction
                      endpoint={`/cities/${city.entity_id}/publish`}
                      label="Publish city"
                      compact
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
