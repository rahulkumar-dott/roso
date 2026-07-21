import { getAdminContentSimilarity } from "@/lib/api";
import { StatusBadge } from "../shared";

export default async function AdminSimilarityPage() {
  const similarity = await getAdminContentSimilarity();

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-xl font-semibold text-brand-navy">Similarity Inspector</h2>
      <p className="mt-1 text-sm text-slate-600">
        Canonical / duplicate similarity band computed at draft time for every drafted-content
        entity (Module 3).
      </p>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="py-2 pr-4">Entity</th>
              <th className="py-2 pr-4">Version</th>
              <th className="py-2 pr-4">Band</th>
              <th className="py-2 pr-4">Score</th>
              <th className="py-2 pr-4">Nearest entity</th>
            </tr>
          </thead>
          <tbody>
            {similarity?.items.map((row, index) => (
              <tr key={`${row.entity_id}-${row.version}-${index}`} className="border-b border-slate-100">
                <td className="py-2 pr-4 text-brand-navy">{row.entity_id}</td>
                <td className="py-2 pr-4 text-slate-600">{row.version}</td>
                <td className="py-2 pr-4">
                  <StatusBadge active={row.band === "UNIQUE"} label={row.band ?? "n/a"} />
                </td>
                <td className="py-2 pr-4 text-slate-600">{row.score ?? "n/a"}</td>
                <td className="py-2 pr-4 text-slate-600">{row.nearest_entity_id ?? "-"}</td>
              </tr>
            ))}
            {(!similarity || similarity.items.length === 0) && (
              <tr>
                <td colSpan={5} className="py-3 text-xs text-slate-500">
                  No drafted content with similarity data yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
