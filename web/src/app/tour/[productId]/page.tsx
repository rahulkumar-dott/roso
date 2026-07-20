import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getPublishedTour } from "@/lib/api";
import type { ModelCInfo } from "@/lib/types";

type Props = {
  params: Promise<{ productId: string }>;
};

function isProductModelC(value: unknown): value is ModelCInfo {
  return Boolean(
    value &&
      typeof value === "object" &&
      "reasons" in value &&
      "winner_slots" in value
  );
}

function fallbackImage(seed: string): string {
  return `https://picsum.photos/seed/roso-${encodeURIComponent(seed)}/1200/700`;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { productId } = await params;
  const record = await getPublishedTour(productId);
  if (!record) return { title: "Tour not found" };

  return {
    title: record.content.meta_title,
    description: record.content.meta_description,
    alternates: { canonical: record.content.canonical_url },
  };
}

export default async function TourPage({ params }: Props) {
  const { productId } = await params;
  const record = await getPublishedTour(productId);
  if (!record) notFound();

  const { content } = record;
  const defaultVariant =
    content.variants.find((v) => v.audience === "first_time_visitor") ?? content.variants[0];
  const modelC = isProductModelC(content.model_c) ? content.model_c : null;

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      {/* Structured data exactly as published by the backend's Schema Builder */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(record.schema_json) }}
      />

      <p className="text-sm text-slate-500">
        <Link href="/" className="hover:underline">
          Home
        </Link>
      </p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">{content.h1}</h1>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={content.primary_image ?? fallbackImage(productId)}
          alt=""
          className="h-72 w-full object-cover"
        />
      </div>

      {defaultVariant && (
        <p className="mt-3 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {defaultVariant.snippet_text}
        </p>
      )}

      <ul className="mt-6 flex flex-wrap gap-2">
        {content.highlights.map((highlight) => (
          <li
            key={highlight}
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-sm text-slate-700"
          >
            {highlight}
          </li>
        ))}
      </ul>

      <p className="mt-6 leading-relaxed text-slate-700">{content.body}</p>

      {modelC && (
        <div className="mt-8 rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Why this made the shortlist
          </h2>
          <div className="mt-3 flex flex-wrap gap-1">
            {modelC.reasons.map((reason) => (
              <span
                key={reason}
                className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
              >
                {reason}
              </span>
            ))}
          </div>
          {modelC.winner_slots.length > 0 && (
            <p className="mt-3 text-sm text-slate-600">
              Winning slot(s): {modelC.winner_slots.join(", ")}
            </p>
          )}
        </div>
      )}

      {content.faq.length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold">Frequently asked questions</h2>
          <dl className="mt-4 space-y-4">
            {content.faq.map((item) => (
              <div key={item.question}>
                <dt className="font-medium text-slate-900">{item.question}</dt>
                <dd className="mt-1 text-slate-600">{item.answer}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <p className="mt-10 text-xs text-slate-400">
        Draft version {content.draft_version ?? "n/a"} - published {record.date_published} - canonical{" "}
        {record.canonical_url}
      </p>
    </div>
  );
}
