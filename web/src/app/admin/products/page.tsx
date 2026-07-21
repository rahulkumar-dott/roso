import { getAdminProducts } from "@/lib/api";
import { AdminAction, ProductDebugPanel } from "../AdminActions";
import { StatusBadge } from "../shared";

export default async function AdminProductsPage() {
  const products = await getAdminProducts();

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
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
                <td className="py-3 pr-4 text-slate-600">{product.quality_score ?? "n/a"}</td>
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
                  <div className="mt-2">
                    <ProductDebugPanel entityId={product.entity_id} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
