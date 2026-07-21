import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getAdminPendingDestinations,
  getAuditLog,
  getDestinationsTree,
  getPublishedRecord,
} from "@/lib/api";
import {
  AdminAction,
  ContentLockForm,
  HeroImageForm,
  MergeDestinationForm,
  type HeroImageValue,
} from "../../AdminActions";
import { StatusBadge } from "../../shared";

type Props = {
  params: Promise<{ countrySlug: string }>;
};

export default async function AdminCountryDetailPage({ params }: Props) {
  const { countrySlug } = await params;
  const tree = await getDestinationsTree();
  const country = tree?.countries.find((c) => c.slug === countrySlug);
  if (!country) notFound();

  const [record, pending, auditLog] = await Promise.all([
    getPublishedRecord(country.entity_id),
    getAdminPendingDestinations(),
    getAuditLog(50, country.entity_id),
  ]);

  const pendingRow = pending?.pending.find((row) => row.entity_id === country.entity_id) ?? null;

  const lockedFields = Object.entries(record?.content_locks ?? {})
    .filter(([, meta]) => meta && typeof meta === "object" && meta.locked)
    .map(([field]) => field);

  const candidateFields = Object.keys(record?.content_candidates ?? {});

  return (
    <div className="space-y-6">
      <div>
        <Link href="/admin/countries" className="text-xs text-brand-primary hover:underline">
          ← All countries
        </Link>
      </div>

      {/* 1. Header strip */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-brand-navy">{country.name}</h1>
            <a href={country.canonical_url} className="text-xs text-brand-primary hover:underline">
              {country.canonical_url}
            </a>
          </div>
          <div className="flex flex-wrap gap-2">
            {record && <StatusBadge active={record.status === "published"} label={record.status} />}
            {record && (
              <StatusBadge
                active={record.index_state === "indexed"}
                label={record.index_state === "indexed" ? "Indexed" : "Noindex (not promoted)"}
              />
            )}
            {pendingRow && <StatusBadge active={false} label="Pending review" />}
          </div>
        </div>
        {record && (
          <p className="mt-2 text-xs text-slate-500">
            Published {record.date_published} - last modified {record.date_modified}
          </p>
        )}
      </section>

      {/* 2. Pending-review actions */}
      {pendingRow && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-5">
          <h2 className="text-sm font-semibold text-amber-800">
            This country is pending review (synced from Viator, not yet approved)
          </h2>
          {pendingRow.possible_duplicate_of && (
            <p className="mt-1 text-xs text-amber-700">
              Possible duplicate of {pendingRow.possible_duplicate_of}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <AdminAction endpoint={`/admin/destinations/${pendingRow.entity_id}/approve`} label="Approve" compact />
            <AdminAction endpoint={`/admin/destinations/${pendingRow.entity_id}/reject`} label="Reject" compact />
          </div>
          <div className="mt-3">
            <MergeDestinationForm
              entityId={pendingRow.entity_id}
              defaultCanonicalId={pendingRow.possible_duplicate_of ?? ""}
            />
          </div>
        </section>
      )}

      {/* 3. Publish / Promote */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-brand-navy">Publish / Promote</h2>
        <p className="mt-1 text-xs text-slate-600">
          Publish recomputes content and schema from current source data. Promote flips a
          published country from noindex,follow to indexed (WBS Lite Page governance) - a
          one-time manual gate, never automatic.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <AdminAction endpoint={`/countries/${encodeURIComponent(country.name)}/publish`} label="Publish" compact />
          {record && record.index_state !== "indexed" && (
            <AdminAction
              endpoint={`/countries/${encodeURIComponent(country.name)}/promote`}
              label="Promote to indexed"
              compact
            />
          )}
        </div>
      </section>

      {/* Cities under this country - cross-link into their own unified screens */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-brand-navy">Cities in {country.name}</h2>
        {country.cities.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {country.cities.map((city) => (
              <Link
                key={city.entity_id}
                href={`/admin/cities/${city.entity_id}`}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-brand-navy hover:border-brand-primary hover:bg-white"
              >
                {city.name}
              </Link>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-xs text-slate-500">No active cities under this country yet.</p>
        )}
      </section>

      {!record ? (
        <section className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-500">
          Not published yet - use Publish above, then the hero image and content editing sections
          will appear here.
        </section>
      ) : (
        <>
          {/* 4. Hero image */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-brand-navy">Hero image</h2>
            <HeroImageForm
              entityId={country.entity_id}
              entityType="country"
              liveHeroImage={record.content.hero_image as HeroImageValue | null | undefined}
              candidate={record.content_candidates?.hero_image}
            />
          </section>

          {/* 5. Content fields */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-brand-navy">Content</h2>
            <ContentLockForm
              entityId={country.entity_id}
              lockedFields={lockedFields}
              liveContent={record.content as unknown as Record<string, unknown>}
              candidates={record.content_candidates}
            />
          </section>

          {/* 6. Governance summary */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-brand-navy">Governance status</h2>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Locked fields
                </p>
                {lockedFields.length > 0 ? (
                  <ul className="mt-1 list-inside list-disc text-sm text-slate-700">
                    {lockedFields.map((field) => (
                      <li key={field}>{field}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-xs text-slate-500">None locked.</p>
                )}
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Pending candidates
                </p>
                {candidateFields.length > 0 ? (
                  <ul className="mt-1 list-inside list-disc text-sm text-slate-700">
                    {candidateFields.map((field) => (
                      <li key={field}>{field}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-xs text-slate-500">None pending.</p>
                )}
              </div>
            </div>

            {!country.cities.length && record.index_state === "noindex" && (
              <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3">
                <p className="text-xs font-semibold text-amber-800">
                  This country has zero active cities right now.
                </p>
                <p className="mt-1 text-xs text-amber-700">
                  If it was previously indexed, publishing again will auto-demote it to noindex
                  (logged below) rather than leave an empty page live.
                </p>
              </div>
            )}

            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Audit log for this country
              </p>
              <div className="mt-2 overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="py-1.5 pr-4">When</th>
                      <th className="py-1.5 pr-4">Actor</th>
                      <th className="py-1.5 pr-4">Action</th>
                      <th className="py-1.5 pr-4">Field</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLog?.entries.map((entry) => (
                      <tr key={entry.id} className="border-b border-slate-100">
                        <td className="py-1.5 pr-4 text-slate-500">{entry.created_at}</td>
                        <td className="py-1.5 pr-4 text-slate-600">{entry.actor}</td>
                        <td className="py-1.5 pr-4 text-brand-navy">{entry.action}</td>
                        <td className="py-1.5 pr-4 text-slate-600">{entry.field ?? "-"}</td>
                      </tr>
                    ))}
                    {(!auditLog || auditLog.entries.length === 0) && (
                      <tr>
                        <td colSpan={4} className="py-3 text-xs text-slate-500">
                          No audit entries for this country yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
