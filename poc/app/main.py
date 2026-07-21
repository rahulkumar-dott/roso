from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.db import Base, engine, ensure_schema_compatibility
from app.routers import (
    admin,
    decisions,
    drafting,
    enrichment,
    entities,
    ingestion,
    keyword_intel,
    llm_visibility,
    mcp,
    publishing,
)

Base.metadata.create_all(bind=engine)
ensure_schema_compatibility()

app = FastAPI(
    title="Rosotravel AI Platform - POC",
    description=(
        "Phase 1: Data Ingestion & Versioning Engine. "
        "Phase 2: Factual Enrichment. "
        "Phase 3: AI Drafting Pipeline. "
        "Phase 4: Model C Decision Engine. "
        "Phase 5: Schema Publishing. "
        "Phase 6: LLM Visibility. "
        "Phase 7: Real Integration Swap-In."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router)
app.include_router(admin.router)
app.include_router(entities.router)
app.include_router(enrichment.router)
app.include_router(drafting.router)
app.include_router(keyword_intel.router)
app.include_router(decisions.router)
app.include_router(publishing.router)
app.include_router(llm_visibility.router)
app.include_router(mcp.router)

static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
