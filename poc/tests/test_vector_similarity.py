from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.services import vector_similarity


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_vector_literal_formats_pgvector_cast_value():
    values = [0.1, 0.25, -0.333333333]

    assert vector_similarity.vector_literal(values) == "[0.10000000,0.25000000,-0.33333333]"


def test_pgvector_similarity_returns_none_on_sqlite():
    db = make_session()

    assert vector_similarity.nearest_by_pgvector(db, "entity", "body") is None


def test_hash_embedding_is_normalized_and_stable():
    embedder = vector_similarity.HashEmbeddingAdapter()

    first = embedder.embed("colosseum tickets")
    second = embedder.embed("colosseum tickets")

    assert first == second
    assert len(first) == vector_similarity.EMBEDDING_DIM
    assert round(sum(value * value for value in first), 6) == 1.0
