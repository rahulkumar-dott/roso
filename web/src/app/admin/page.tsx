import Link from "next/link";
import {
  getAdminContent,
  getAdminDestinations,
  getAdminOverview,
  getAdminProducts,
  getAdminPublishing,
} from "@/lib/api";
import { AdminAction, CreateCountryForm } from "./AdminActions";

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-brand-navy">{value}</p>
    </div>
  );
}

function StatusBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
        active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
      }`}
    >
      {label}
    </span>
  );
}

export default async function AdminPage() {
  const [overview, destinations, products, content, publishing] = await Promise.all([
    getAdminOverview(),
    getAdminDestinations(),
    getAdminProducts(),
    getAdminContent(),
    getAdminPublishing(),
  ]);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">
            <Link href="/" className="hover:underline">
              Home
            </Link>{" "}
            / Admin
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-brand-navy">
            Admin Control Center
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-600">
            POC admin for destination publishing, Product Ops Set control, AI content status, and
            SEO publishing records. Labels separate recomputing decisions from generating AI drafts.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <AdminAction endpoint="/model-c/recompute" label="Recompute decisions" compact />
          <AdminAction endpoint="/model-c/bulk-auto-confirm" label="Auto-confirm Pool to Set" compact />
        </div>
      </div>

      {overview && (
        <section className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-7">
          <Stat label="Destinations" value={overview.destinations} />
          <Stat label="Products" value={overview.products} />
          <Stat label="Published" value={overview.published_records} />
          <Stat label="Validated drafts" value={overview.drafts_validated} />
          <Stat label="Failed drafts" value={overview.drafts_failed} />
          <Stat label="Pool" value={overview.pool_products} />
          <Stat label="Set" value={overview.set_products} />
        </section>
      )}

      <section className="mt-10 rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-xl font-semibold text-brand-navy">Destinations</h2>
        <p className="mt-1 text-sm text-slate-600">
          Country and city page publishing. Country click routes travelers to country pages; city
          click routes to city decision hubs.
        </p>
        <div className="mt-4">
          <CreateCountryForm />
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
                    <span className="text-xs text-slate-500">{country.cities.length} cities</span>
                  </div>
                </div>
                <AdminAction
                  endpoint={`/countries/${encodeURIComponent(country.country)}/publish`}
                  label="Publish country page"
                  compact
                />
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                {country.cities.map((city) => (
                  <div key={city.entity_id} className="rounded-md bg-slate-50 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-medium text-brand-navy">{city.name}</p>
                        <p className="text-xs text-slate-500">
                          {city.products_count} products, {city.picks_count} picks
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

      <section className="mt-10 rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-xl font-semibold text-brand-navy">Products / Model C</h2>
        <p className="mt-1 text-sm text-slate-600">
          Product Ops controls Pool/Set state. Recompute decisions updates scores and archetypes;
          it does not generate AI text.
        </p>
        <div className="mt-5 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="py-2 pr-4">Product</th>
                <th className="py-2 pr-4">City</th>
                <th className="py-2 pr-4">Quality</th>
                <th className="py-2 pr-4">Pool / Set</th>
                <th className="py-2 pr-4">Draft</th>
                <th className="py-2 pr-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products?.products.slice(0, 30).map((product) => (
                <tr key={product.entity_id} className="border-b border-slate-100">
                  <td className="py-3 pr-4">
                    <p className="font-medium text-brand-navy">{product.name}</p>
                    <p className="text-xs text-slate-500">{product.entity_id}</p>
                  </td>
                  <td className="py-3 pr-4 text-slate-600">{product.city ?? "Unlinked"}</td>
                  <td className="py-3 pr-4 text-slate-600">
                    {product.quality_score ?? "n/a"}
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex flex-wrap gap-1">
                      <StatusBadge active={product.in_pool} label="Pool" />
                      <StatusBadge active={product.in_set} label="Set" />
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-slate-600">{product.draft_status ?? "none"}</td>
                  <td className="py-3 pr-4">
                    <div className="flex flex-wrap gap-2">
                      <AdminAction
                        endpoint={`/products/${product.entity_id}/set`}
                        label={product.in_set ? "Remove Set" : "Add Set"}
                        body={{ in_set: !product.in_set, confirmed_by: "admin_poc" }}
                        compact
                      />
                      <AdminAction endpoint={`/entities/${product.entity_id}/draft`} label="Generate draft" compact />
                      <AdminAction endpoint={`/entities/${product.entity_id}/publish`} label="Publish product" compact />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-10 grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="text-xl font-semibold text-brand-navy">AI Content</h2>
          <div className="mt-4 space-y-3">
            {content?.items.slice(0, 12).map((item) => (
              <div key={item.entity_id} className="rounded-md bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-brand-navy">{item.name}</p>
                    <p className="text-xs text-slate-500">
                      severity {item.latest_severity ?? "n/a"} - variants {item.variant_count}
                    </p>
                    {item.validation_errors.length > 0 && (
                      <p className="mt-1 text-xs text-red-600">{item.validation_errors.join(", ")}</p>
                    )}
                  </div>
                  <StatusBadge active={item.draft_status === "validated"} label={item.draft_status ?? "none"} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="text-xl font-semibold text-brand-navy">Publishing / SEO</h2>
          <div className="mt-4 space-y-3">
            {publishing?.records.slice(0, 14).map((record) => (
              <div key={record.entity_id} className="rounded-md bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-brand-navy">{record.name}</p>
                    <p className="text-xs text-slate-500">
                      {record.entity_type} - JSON-LD nodes {record.json_ld_nodes}
                    </p>
                    <a
                      href={record.canonical_url}
                      className="mt-1 block truncate text-xs text-brand-primary"
                    >
                      {record.canonical_url}
                    </a>
                  </div>
                  <StatusBadge active={record.status === "published"} label={record.status} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
