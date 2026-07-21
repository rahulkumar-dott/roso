import { getAdminContent, getAdminPublishing, getPublishedList } from "@/lib/api";
import { ContentCountryBrowser, type ContentBrowserRow } from "../ContentBrowser";
import { StatusBadge } from "../shared";

export default async function AdminContentPage() {
  const [content, publishing, publishedList] = await Promise.all([
    getAdminContent(),
    getAdminPublishing(),
    getPublishedList(200),
  ]);

  const liveContentByEntity: Record<string, Record<string, unknown>> = {};
  const candidatesByEntity: Record<string, Record<string, { value: unknown; generated_at?: string }>> = {};
  for (const record of publishedList?.records ?? []) {
    liveContentByEntity[record.entity_id] = record.content as unknown as Record<string, unknown>;
    if (record.content_candidates) {
      candidatesByEntity[record.entity_id] = record.content_candidates;
    }
  }

  const rows: ContentBrowserRow[] = (publishing?.records ?? []).map((record) => ({
    ...record,
    countrySlug:
      (liveContentByEntity[record.entity_id]?.country_slug as string | undefined) ??
      (record.entity_type === "country" ? record.entity_id.replace(/^country_/, "") : null),
  }));

  return (
    <div className="grid gap-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-xl font-semibold text-brand-navy">AI Content</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
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
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-xl font-semibold text-brand-navy">Publishing / SEO</h2>
        <p className="mt-1 text-sm text-slate-600">
          Pick a country to see its own editable content plus every published city underneath it.
        </p>
        <div className="mt-4">
          <ContentCountryBrowser
            rows={rows}
            liveContentByEntity={liveContentByEntity}
            candidatesByEntity={candidatesByEntity}
          />
        </div>
      </section>
    </div>
  );
}
