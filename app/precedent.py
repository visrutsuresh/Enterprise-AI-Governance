import os
from pathlib import Path

import weaviate
from fastembed import TextEmbedding
from weaviate.classes.config import DataType, Property
from weaviate.classes.query import Filter, MetadataQuery

COLLECTION = "Precedent"  # past governance decisions, searched by the inspectors (FR-10)
RELEVANCE_FLOOR = 60  # below this, a hit is off-topic noise, not precedent

WEAVIATE_PORT = int(os.getenv("WEAVIATE_PORT", "8082"))  # #6's own local Weaviate (see docker-compose.yml), #4 holds 8081
WEAVIATE_GRPC = int(os.getenv("WEAVIATE_GRPC", "50053"))

_model = None  # loaded on first use so a plain import stays instant


def _client():
    # WEAVIATE_URL + WEAVIATE_API_KEY switch to Weaviate Cloud (the deployed path)
    url = os.getenv("WEAVIATE_URL")
    if url:
        from weaviate.classes.init import Auth

        return weaviate.connect_to_weaviate_cloud(
            cluster_url=url, auth_credentials=Auth.api_key(os.getenv("WEAVIATE_API_KEY", ""))
        )
    return weaviate.connect_to_local(host=os.getenv("WEAVIATE_HOST", "localhost"), port=WEAVIATE_PORT, grpc_port=WEAVIATE_GRPC)


def embed(text: str) -> list[float]:
    # turn text into 384 numbers that encode what it is about
    global _model
    if _model is None:
        # bge-small-en-v1.5; the first ever call downloads it. Cache lives in the
        # repo (gitignored), not the OS temp dir: temp caches got corrupted once
        # and a wiped temp would re-download mid-demo.
        cache = Path(__file__).resolve().parent.parent / ".fastembed_cache"
        _model = TextEmbedding(cache_dir=str(cache))
    return list(_model.embed([text]))[0].tolist()


def ensure_collection() -> None:
    # create the Precedent drawer if this Weaviate has never seen it
    client = _client()
    try:
        if not client.collections.exists(COLLECTION):
            client.collections.create(
                COLLECTION,
                properties=[
                    Property(name="title", data_type=DataType.TEXT),
                    Property(name="content", data_type=DataType.TEXT),
                    Property(name="source", data_type=DataType.TEXT),
                ],
            )
    finally:
        client.close()


def search(query: str, k: int = 5) -> list[dict]:
    client = _client()
    try:
        col = client.collections.get(COLLECTION)
        vec = embed(query)
        results = col.query.near_vector(near_vector=vec, limit=k, return_metadata=MetadataQuery(distance=True))
        out = []
        for o in results.objects:
            d = dict(o.properties)
            dist = o.metadata.distance or 0.0
            d["score"] = round((1 - dist / 2) * 100, 1)  # cosine distance to 0..100 relevance
            out.append(d)
        return [h for h in out if h["score"] >= RELEVANCE_FLOOR]
    finally:
        client.close()


def index_decision(title: str, content: str, source: str = "pipeline") -> None:
    # file one governance decision so future assessments can cite it.
    # source "pipeline" is a real assessed asset; "seed" is the starter set
    # from seed_precedent.py. Only the seed is ever bulk-deleted (D44).
    client = _client()
    try:
        col = client.collections.get(COLLECTION)
        col.data.insert(
            properties={"title": title, "content": content, "source": source},
            vector=embed(title + ". " + content),
        )
    finally:
        client.close()


def clear_seeded() -> int:
    # drop ONLY the seeded rows, never a real filed decision
    client = _client()
    try:
        col = client.collections.get(COLLECTION)
        res = col.data.delete_many(where=Filter.by_property("source").equal("seed"))
        return res.successful
    finally:
        client.close()
