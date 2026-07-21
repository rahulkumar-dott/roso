import Link from "next/link";

const ADMIN_TABS = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/countries", label: "Countries" },
  { href: "/admin/cities", label: "Cities" },
  { href: "/admin/destinations", label: "Destinations" },
  { href: "/admin/products", label: "Products / Model C" },
  { href: "/admin/content", label: "Content & Publishing" },
  { href: "/admin/similarity", label: "Similarity Inspector" },
  { href: "/admin/site-config", label: "Site Config" },
  { href: "/admin/audit-log", label: "Audit Log" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
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
        Document-aligned admin foundation for taxonomy, Product Ops, AI content, and publishing
        governance.
      </p>

      <nav className="mt-6 flex flex-wrap gap-1 border-b border-slate-200">
        {ADMIN_TABS.map((tab) => (
          <Link
            key={tab.href}
            href={tab.href}
            className="rounded-t-md px-4 py-2 text-sm font-medium text-brand-navy/70 hover:bg-slate-50 hover:text-brand-primary"
          >
            {tab.label}
          </Link>
        ))}
      </nav>

      <div className="mt-6">{children}</div>
    </div>
  );
}
