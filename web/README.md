# Rosotravel AI Platform - Demo Frontend

Minimal Next.js (App Router, TypeScript, Tailwind) storefront that server-renders pages
directly from the `poc/` FastAPI backend, so the AI-generated content, decision-proof
reasoning, and schema.org markup are visible in real page source - not just an API response.

Pages:

- `/` - destination list
- `/country/[countrySlug]` - country page with city choices and published country content when available
- `/city/[cityId]` - published city content + Model C picks (best value / premium / rails) for a
  city, linking to each pick's tour page
- `/tour/[productId]` - full published tour: AI-drafted content, one audience snippet, FAQ,
  Model C reason codes, and the backend's JSON-LD injected into a `<script type="application/
  ld+json">` tag
- `/admin` - POC admin dashboard for destinations, Product Ops / Model C, AI content, and publishing

## Setup

```bash
cd web
npm install
cp .env.local.example .env.local   # points at http://127.0.0.1:8000 by default
```

## Run

Backend must be running first (see `../poc/README.md`). Then, with demo data seeded (see
below):

```bash
npm run dev
```

Open http://localhost:3000.

## Seeding demo data

The frontend expects published country, city, and tour records under `country_*`, `demo_dest_*`,
and `demo_prod_*` entity IDs (see `src/lib/destinations.ts`). Populate them with the backend's
seed script, which ingests fresh destinations/products, runs Model C, publishes country/city
pages, and drafts + publishes every product:

```bash
cd ../poc
uv run python scripts/seed_demo.py
```

The first draft call loads a local sentence-transformer model and may call live Groq/Google
Places APIs if configured, so it can take a minute or two on a cold start.
