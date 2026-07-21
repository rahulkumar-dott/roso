import type { Metadata } from "next";
import Link from "next/link";
import { getAdminSiteConfig, getDestinationsTree } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rosotravel - AI Decision Platform Demo",
  description:
    "Proof-of-concept storefront rendering Rosotravel's AI-curated tour picks, decision-proof content, and schema.org data live from the backend.",
};

type MenuLink = { label: string; url: string };

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [tree, siteConfig] = await Promise.all([getDestinationsTree(), getAdminSiteConfig()]);
  const countries = tree?.countries ?? [];

  const headerNavMenu = ((siteConfig?.header_nav_menu as MenuLink[] | undefined) ?? []) as MenuLink[];
  const footerSections = ((siteConfig?.footer_sections as Record<string, MenuLink[]> | undefined) ?? {}) as Record<
    string,
    MenuLink[]
  >;

  return (
    <html lang="en" className="h-full antialiased font-sans">
      <body className="min-h-full flex flex-col bg-white text-brand-navy">
        <div className="bg-brand-navy py-1.5 text-center text-xs text-white/80">
          Proof-of-concept demo - AI-generated content, not the live rosotravel.com site
        </div>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link href="/" className="text-xl font-bold tracking-tight text-brand-navy">
              Roso<span className="text-brand-primary">travel</span>
            </Link>
            <nav className="hidden items-center gap-8 text-sm font-medium text-brand-navy/80 sm:flex">
              {headerNavMenu.map((item) =>
                item.label === "Destinations" ? (
                  <div key={item.label} className="group relative py-2">
                    <Link href={item.url} className="hover:text-brand-primary">
                      {item.label}
                    </Link>
                    <div className="invisible absolute left-0 top-full z-30 w-64 translate-y-2 rounded-lg border border-slate-200 bg-white py-2 opacity-0 shadow-lg transition group-hover:visible group-hover:translate-y-0 group-hover:opacity-100">
                      {countries.map((country) => (
                        <div key={country.slug} className="group/country relative">
                          <Link
                            href={`/country/${country.slug}`}
                            className="flex items-center justify-between px-4 py-2.5 text-sm text-brand-navy hover:bg-slate-50 hover:text-brand-primary"
                          >
                            <span>{country.name}</span>
                            <span className="text-slate-300">›</span>
                          </Link>
                          <div className="invisible absolute left-full top-0 z-40 w-56 translate-x-2 rounded-lg border border-slate-200 bg-white py-2 opacity-0 shadow-lg transition group-hover/country:visible group-hover/country:translate-x-0 group-hover/country:opacity-100">
                            {country.cities.map((city) => (
                              <Link
                                key={city.entity_id}
                                href={`/city/${city.entity_id}`}
                                className="block px-4 py-2.5 text-sm text-brand-navy hover:bg-slate-50 hover:text-brand-primary"
                              >
                                {city.name}
                              </Link>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <Link key={item.label} href={item.url} className="hover:text-brand-primary">
                    {item.label}
                  </Link>
                ),
              )}
              <Link href="/admin" className="hover:text-brand-primary">
                Admin
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1 bg-slate-50">{children}</main>
        <footer className="border-t border-slate-200 bg-brand-navy py-10 text-white/70">
          <div className="mx-auto max-w-6xl px-6">
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(footerSections).map(([sectionLabel, links]) => (
                <div key={sectionLabel}>
                  <p className="text-xs font-semibold uppercase tracking-wide text-white/50">
                    {sectionLabel}
                  </p>
                  <ul className="mt-3 space-y-2">
                    {links.map((link) => (
                      <li key={link.label}>
                        <Link href={link.url} className="text-sm hover:text-white">
                          {link.label}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <div className="mt-8 border-t border-white/10 pt-6 text-center text-sm">
              <p>Rosotravel AI Decision Platform - proof of concept.</p>
              <p className="mt-1 text-xs text-white/50">
                Content on this demo is generated by the AI pipeline for illustration only.
              </p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
