import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getDestinationsTree, getPublishedRecord } from "@/lib/api";

type Props = {
  params: Promise<{ countrySlug: string }>;
};

async function findCountry(countrySlug: string) {
  const tree = await getDestinationsTree();
  return tree?.countries.find((c) => c.slug === countrySlug) ?? null;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { countrySlug } = await params;
  const country = await findCountry(countrySlug);
  if (!country) return { title: "Country not found" };

  const record = await getPublishedRecord(country.entity_id);
  return {
    title: record?.content.meta_title ?? `Discover ${country.name} | Rosotravel`,
    description:
      record?.content.meta_description ??
      `Explore ${country.name} through Rosotravel country and city decision pages.`,
    alternates: record ? { canonical: record.canonical_url } : undefined,
  };
}

export default async function CountryPage({ params }: Props) {
  const { countrySlug } = await params;
  const country = await findCountry(countrySlug);
  if (!country) notFound();

  const record = await getPublishedRecord(country.entity_id);
  const content = record?.content;

  return (
    <div>
      {record && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(record.schema_json) }}
        />
      )}

      <section className="bg-gradient-to-br from-brand-navy to-brand-primary-dark py-12 text-white">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-sm text-white/70">
            <Link href="/" className="hover:underline">
              Home
            </Link>{" "}
            / Destinations / {country.name}
          </p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight">
            {content?.h1 ?? `Discover ${country.name}`}
          </h1>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-6 py-10">
        {content?.overview && (
          <section className="mb-8">
            <p className="max-w-3xl leading-relaxed text-slate-700">{content.overview}</p>
          </section>
        )}

        <div className="mb-10 grid gap-6 sm:grid-cols-2">
          {content?.highlights && content.highlights.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-brand-primary-dark">
                Highlights
              </h2>
              <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-slate-700">
                {content.highlights.map((highlight) => (
                  <li key={highlight}>{highlight}</li>
                ))}
              </ul>
            </div>
          )}

          {content?.facts && content.facts.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-brand-primary-dark">
                Facts &amp; Curiosities
              </h2>
              <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-slate-700">
                {content.facts.map((fact) => (
                  <li key={fact}>{fact}</li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-slate-400">Sourced from Wikidata via Viator destination data.</p>
            </div>
          )}
        </div>

        <section className="mb-10">
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl font-semibold text-brand-navy">Cities in {country.name}</h2>
              <p className="mt-1 text-sm text-slate-600">
                Pick a city to open the decision-first city hub.
              </p>
            </div>
            {record && <span className="text-xs text-slate-400">Published {record.date_modified}</span>}
          </div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {country.cities.map((city) => (
              <Link
                key={city.entity_id}
                href={`/city/${city.entity_id}`}
                className="group overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <div className="flex h-28 items-center justify-center bg-gradient-to-br from-brand-primary to-brand-primary-dark text-lg font-semibold text-white">
                  {city.name}
                </div>
                <div className="p-4">
                  <p className="font-medium text-brand-navy group-hover:text-brand-primary">
                    {city.name}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">City hub and curated picks</p>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {content?.top_regions && content.top_regions.length > 0 && (
          <section className="mb-10">
            <h2 className="text-2xl font-semibold text-brand-navy">Regions of {country.name}</h2>
            <p className="mt-1 text-sm text-slate-600">
              Real regions from Viator&apos;s destination taxonomy - no dedicated region pages yet.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {content.top_regions.map((region) => (
                <span
                  key={region.entity_id}
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700"
                >
                  {region.name}
                </span>
              ))}
            </div>
          </section>
        )}

        {content?.faq && content.faq.length > 0 && (
          <section className="mt-10">
            <h2 className="text-xl font-semibold">Country planning FAQ</h2>
            <dl className="mt-4 grid gap-4 sm:grid-cols-3">
              {content.faq.map((item) => (
                <div key={item.question} className="rounded-lg border border-slate-200 bg-white p-4">
                  <dt className="font-medium text-slate-900">{item.question}</dt>
                  <dd className="mt-2 text-sm text-slate-600">{item.answer}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}
      </div>
    </div>
  );
}
