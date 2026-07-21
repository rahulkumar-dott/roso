import Link from "next/link";
import { getAdminPendingDestinations, getAdminPublishing, getDestinationsTree } from "@/lib/api";
import { StatusBadge } from "../shared";

export default async function AdminCitiesPage() {
  const [tree, publishing, pending] = await Promise.all([
    getDestinationsTree(),
    getAdminPublishing(),
    getAdminPendingDestinations(),
  ]);

  const publishedByEntity = new Map((publishing?.records ?? []).map((row) => [row.entity_id, row]));
  const pendingCities = (pending?.pending ?? []).filter(
    (row) => row.destination_level !== "COUNTRY" && row.destination_level !== "REGION",
  );
  const pendingCityIds = new Set(pendingCities.map((row) => row.entity_id));

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-xl font-semibold text-brand-navy">Cities</h2>
      <p className="mt-1 text-sm text-slate-600">
        One screen per city: approve/reject/merge (if pending), publish, hero image upload,
        content editing, and governance status. City hero images are uploaded CMS media only -
        never AI-generated, per the WBS.
      </p>

      {pendingCities.length > 0 && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-4">
          <p className="text-xs font-semibold text-amber-800">Pending review (not yet approved)</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {pendingCities.map((row) => (
              <Link
                key={row.entity_id}
                href={`/admin/cities/${row.entity_id}`}
                className="rounded-full border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100"
              >
                {row.name} ({row.country})
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 space-y-5">
        {tree?.countries.map((country) => (
          <div key={country.entity_id}>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {country.name}
            </p>
            <div className="mt-2 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {country.cities.map((city) => {
                const row = publishedByEntity.get(city.entity_id);
                const isPending = pendingCityIds.has(city.entity_id);
                return (
                  <Link
                    key={city.entity_id}
                    href={`/admin/cities/${city.entity_id}`}
                    className="rounded-lg border border-slate-200 bg-slate-50 p-4 transition hover:border-brand-primary hover:bg-white"
                  >
                    <p className="font-medium text-brand-navy">{city.name}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {row ? (
                        <StatusBadge active={row.status === "published"} label={row.status} />
                      ) : (
                        <StatusBadge active={false} label="Not published" />
                      )}
                      {isPending && <StatusBadge active={false} label="Pending review" />}
                    </div>
                  </Link>
                );
              })}
              {country.cities.length === 0 && (
                <p className="text-xs text-slate-500">No published cities under {country.name} yet.</p>
              )}
            </div>
          </div>
        ))}
        {(!tree || tree.countries.length === 0) && (
          <p className="text-xs text-slate-500">No cities found.</p>
        )}
      </div>
    </section>
  );
}
