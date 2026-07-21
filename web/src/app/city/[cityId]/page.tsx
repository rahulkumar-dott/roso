import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { BROWSER_API_BASE_URL, getCityPicks, getPublishedRecord } from "@/lib/api";
import type { CityPick } from "@/lib/types";

const SLOT_LABELS: Record<string, string> = {
  best_value: "Best Value",
  premium: "Premium Pick",
};

function slotLabel(slot: string): string {
  return SLOT_LABELS[slot] ?? (slot.startsWith("rail_") ? "Also Popular" : slot);
}

function archetypeLabel(archetype: string): string {
  return archetype
    .split("__")
    .slice(1)
    .join(" ")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase()) || archetype;
}

function fallbackImage(seed: string): string {
  return `https://picsum.photos/seed/roso-${encodeURIComponent(seed)}/900/600`;
}

type Props = {
  params: Promise<{ cityId: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { cityId } = await params;
  const record = await getPublishedRecord(cityId);
  if (!record) return { title: "City not found" };

  return {
    title: record.content.meta_title,
    description: record.content.meta_description,
    alternates: { canonical: record.canonical_url },
  };
}

export default async function CityPage({ params }: Props) {
  const { cityId } = await params;
  const [picks, record] = await Promise.all([getCityPicks(cityId), getPublishedRecord(cityId)]);
  if (!record) notFound();

  const content = record.content;
  const cityName = content.city_name ?? content.h1;
  const countryName = content.country_name;
  const countrySlug = content.country_slug;

  return (
    <div>
      {record && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(record.schema_json) }}
        />
      )}

      <section
        className="relative bg-gradient-to-br from-brand-primary to-brand-primary-dark bg-cover bg-center py-12 text-white"
        style={
          content?.hero_image?.url
            ? { backgroundImage: `url(${BROWSER_API_BASE_URL}${content.hero_image.url})` }
            : undefined
        }
      >
        {content?.hero_image?.url && (
          <div className="absolute inset-0 bg-brand-navy/60" aria-hidden="true" />
        )}
        <div className="relative mx-auto max-w-6xl px-6">
          <p className="text-sm text-white/70">
            <Link href="/" className="hover:underline">
              Home
            </Link>{" "}
            / Destinations /{" "}
            {countrySlug ? (
              <Link href={`/country/${countrySlug}`} className="hover:underline">
                {countryName}
              </Link>
            ) : (
              countryName
            )}{" "}
            / {cityName}
          </p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight">{content.h1}</h1>
          <p className="mt-2 max-w-2xl text-white/80">{content.body}</p>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-6 py-10">
        {content?.overview && (
          <section className="mb-8">
            <p className="max-w-3xl leading-relaxed text-slate-700">{content.overview}</p>
          </section>
        )}

        {content?.highlights && content.highlights.length > 0 && (
          <ul className="mb-8 flex flex-wrap gap-2">
            {content.highlights.map((highlight) => (
              <li
                key={highlight}
                className="rounded-full border border-slate-200 bg-white px-3 py-1 text-sm text-slate-700"
              >
                {highlight}
              </li>
            ))}
          </ul>
        )}

        {((content?.about_rosotravel) || (content?.local_tips && content.local_tips.length > 0)) && (
          <div className="mb-10 grid gap-6 sm:grid-cols-2">
            {content?.about_rosotravel && (
              <div className="rounded-xl border border-slate-200 bg-white p-6">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-brand-primary-dark">
                  About Rosotravel in {cityName}
                </h2>
                <p className="mt-3 text-sm leading-relaxed text-slate-700">{content.about_rosotravel}</p>
              </div>
            )}

            {content?.local_tips && content.local_tips.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-6">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-brand-primary-dark">
                  Local Tips
                </h2>
                <ul className="mt-3 list-inside list-disc space-y-2 text-sm text-slate-700">
                  {content.local_tips.map((tip) => (
                    <li key={tip}>{tip}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {!picks || picks.suppressed ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-slate-600">
            <p className="font-medium">No curated picks published for {cityName} yet.</p>
            <p className="mt-1 text-sm">
              {picks?.reason ??
                "Model C hasn't confirmed enough Set products for this city, or nothing has been ingested/published yet."}
            </p>
          </div>
        ) : (
          <>
            <div className="rounded-xl border border-brand-primary/20 bg-brand-primary/5 p-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-brand-primary-dark">
                Why you see this shortlist
              </h2>
              <p className="mt-2 text-brand-navy">{picks.decision_proof.shortlist_reason}</p>

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {picks.decision_proof.why_these_picks.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-brand-navy/60">
                      Why these picks
                    </h3>
                    <ul className="mt-1 list-inside list-disc text-sm text-brand-navy/80">
                      {picks.decision_proof.why_these_picks.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {picks.decision_proof.what_we_skipped.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-brand-navy/60">
                      What we skipped
                    </h3>
                    <ul className="mt-1 list-inside list-disc text-sm text-brand-navy/80">
                      {picks.decision_proof.what_we_skipped.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {picks.picks.map((pick: CityPick) => (
                <Link
                  key={pick.product_id}
                  href={`/tour/${pick.product_id}`}
                  className="group overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
                >
                  <div className="relative h-40 overflow-hidden bg-gradient-to-br from-brand-navy to-brand-primary-dark">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={pick.image_url ?? fallbackImage(pick.product_id)}
                      alt=""
                      className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
                    />
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-4">
                      <p className="line-clamp-2 text-sm font-semibold text-white">{pick.title}</p>
                    </div>
                    <span className="absolute left-3 top-3 rounded-full bg-brand-accent px-3 py-1 text-xs font-semibold text-white">
                      {slotLabel(pick.slot)}
                    </span>
                  </div>
                  <div className="p-4">
                    <h3 className="font-semibold text-brand-navy group-hover:text-brand-primary">
                      {pick.title}
                    </h3>
                    {pick.price_from && pick.currency && (
                      <p className="mt-1 text-sm font-medium text-brand-primary-dark">
                        From {pick.price_from} {pick.currency}
                      </p>
                    )}
                    <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">
                      {archetypeLabel(pick.archetype)}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1">
                      {pick.reason_codes.map((code) => (
                        <span
                          key={code}
                          className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                        >
                          {code.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </>
        )}

        {content?.faq && content.faq.length > 0 && (
          <section className="mt-10">
            <h2 className="text-xl font-semibold">City planning FAQ</h2>
            <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
