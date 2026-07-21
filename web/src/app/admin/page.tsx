import { getAdminOverview } from "@/lib/api";
import { AdminAction } from "./AdminActions";
import { Stat } from "./shared";

export default async function AdminOverviewPage() {
  const overview = await getAdminOverview();

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-brand-navy">Overview</h2>
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
    </div>
  );
}
