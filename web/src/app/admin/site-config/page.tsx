import { getAdminSiteConfig } from "@/lib/api";
import { SiteConfigForm } from "../AdminActions";

export default async function AdminSiteConfigPage() {
  const siteConfig = await getAdminSiteConfig();

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-xl font-semibold text-brand-navy">Global Components / Site Config</h2>
      <p className="mt-1 text-sm text-slate-600">
        Site-wide chrome: header/footer menu configuration and cookie/chat toggles (Module 8).
        Edit the JSON value and save.
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {siteConfig &&
          Object.entries(siteConfig).map(([key, value]) => (
            <SiteConfigForm key={key} configKey={key} initialValue={value} />
          ))}
        {!siteConfig && <p className="text-xs text-slate-500">Site config unavailable.</p>}
      </div>
    </section>
  );
}
