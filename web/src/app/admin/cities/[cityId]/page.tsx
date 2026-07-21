import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getAdminPendingDestinations,
  getAuditLog,
  getPublishedRecord,
} from "@/lib/api";
import {
  AdminAction,
  ContentLockForm,
  HeroImageForm,
  MergeDestinationForm,
  QaBatchForm,
  type HeroImageValue,
  type PendingBatch,
} from "../../AdminActions";
import { StatusBadge } from "../../shared";

type Props = {
  params: Promise<{ cityId: string }>;
};

export default async function AdminCityDetailPage({ params }: Props) {
  const { cityId } = await params;

  const [record, pending, auditLog] = await Promise.all([
    getPublishedRecord(cityId),
    getAdminPendingDestinations(),
    getAuditLog(50, cityId),
  ]);

  const pendingRow = pending?.pending.find((row) => row.entity_id === cityId) ?? null;
  if (!record && !pendingRow) notFound();

  const displayName = record?.content.city_name ?? record?.content.h1 ?? pendingRow?.name ?? cityId;
  const countryName = record?.content.country_name ?? pendingRow?.country ?? null;
  const countrySlug = record?.content.country_slug ?? null;

  const lockedFields = Object.entries(record?.content_locks ?? {})
    .filter(([, meta]) => meta && typeof meta === "object" && meta.locked)
    .map(([field]) => field);

  const candidateFields = Object.keys(record?.content_candidates ?? {});

  return (
    <div className="space-y-6">
      <div>
        <Link href="/admin/cities" className="text-xs text-brand-primary hover:underline">
          ← All cities
        </Link>
      </div>

      {/* 1. Header strip */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-brand-navy">{displayName}</h1>
            <p className="text-xs text-slate-500">
              {countrySlug ? (
                <Link href={`/admin/countries/${countrySlug}`} className="text-brand-primary hover:underline">
                  {countryName}
                </Link>
              ) : (
                countryName ?? "Country unknown"
              )}
            </p>
            {record && (
              <a href={record.canonical_url} className="text-xs text-brand-primary hover:underline">
                {record.canonical_url}
              </a>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {record && <StatusBadge active={record.status === "published"} label={record.status} />}
            {record && (
              <StatusBadge active={record.index_state === "indexed"} label={record.index_state ?? "indexed"} />
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
            This city is pending review (synced from Viator, not yet approved)
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
          <p className="mt-3 text-xs text-amber-700">
            A city also needs at least one linked product before Publish will succeed (SOW
            System 1.1 activation gate) - approving alone isn&apos;t enough.
          </p>
        </section>
      )}

      {/* 3. Publish (no Promote step - cities publish straight to indexed, no Lite Page gate) */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-brand-navy">Publish</h2>
        <p className="mt-1 text-xs text-slate-600">
          Recomputes content and schema from current source data. Blocked until the city is
          approved and has at least one linked product - the error will explain which condition
          is unmet. Unlike Country, there is no separate Promote step: a published city goes
          straight to indexed.
        </p>
        <div className="mt-3">
          <AdminAction endpoint={`/cities/${cityId}/publish`} label="Publish" compact />
        </div>
      </section>

      {!record ? (
        <section className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-500">
          Not published yet - use Publish above, then the hero image and content editing sections
          will appear here.
        </section>
      ) : (
        <>
          {/* Run AI Batch / Human QA Sampling (SOW 2.11) */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-brand-navy">Content batch</h2>
            <QaBatchForm
              entityId={cityId}
              liveContent={record.content as unknown as Record<string, unknown>}
              pendingBatch={record.pending_batch as unknown as PendingBatch | null | undefined}
            />
          </section>

          {/* 4. Hero image (upload only - WBS: city hero is real CMS media, never AI-generated) */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-brand-navy">Hero image</h2>
            <HeroImageForm
              entityId={cityId}
              entityType="city"
              liveHeroImage={record.content.hero_image as HeroImageValue | null | undefined}
              candidate={record.content_candidates?.hero_image}
            />
          </section>

          {/* 5. Content fields */}
          <section className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-brand-navy">Content</h2>
            <ContentLockForm
              entityId={cityId}
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

            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Audit log for this city
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
                          No audit entries for this city yet.
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
