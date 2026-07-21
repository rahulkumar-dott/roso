import { getAuditLog } from "@/lib/api";

export default async function AdminAuditLogPage() {
  const auditLog = await getAuditLog(50);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-xl font-semibold text-brand-navy">Audit Log</h2>
      <p className="mt-1 text-sm text-slate-600">
        Recent admin actions: field edits, regenerate/accept/reject/revert, destination
        approve/reject/merge, and site config changes (Module 10).
      </p>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="py-2 pr-4">When</th>
              <th className="py-2 pr-4">Actor</th>
              <th className="py-2 pr-4">Action</th>
              <th className="py-2 pr-4">Entity</th>
              <th className="py-2 pr-4">Field</th>
            </tr>
          </thead>
          <tbody>
            {auditLog?.entries.map((entry) => (
              <tr key={entry.id} className="border-b border-slate-100">
                <td className="py-2 pr-4 text-slate-500">{entry.created_at}</td>
                <td className="py-2 pr-4 text-slate-600">{entry.actor}</td>
                <td className="py-2 pr-4 text-brand-navy">{entry.action}</td>
                <td className="py-2 pr-4 text-slate-600">{entry.entity_id}</td>
                <td className="py-2 pr-4 text-slate-600">{entry.field ?? "-"}</td>
              </tr>
            ))}
            {(!auditLog || auditLog.entries.length === 0) && (
              <tr>
                <td colSpan={5} className="py-3 text-xs text-slate-500">
                  No audit entries yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
