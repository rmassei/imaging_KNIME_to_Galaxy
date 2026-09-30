import os

from dotenv import load_dotenv

from imaging_knime_to_galaxy.llm_client import get_client

load_dotenv()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")


def embed(text: str) -> list[float]:
    """
    Creates an embedding vector for the given text.

    Returns an empty list for empty or whitespace-only input.
    Uses the shared OpenAI client instance from get_client().
    """

    if not text or not text.strip():
        return []
    client = get_client()
    response = client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
    return response.data[0].embedding


def build_doc(owner, name, t):
    parts = [
        t.get("name") or name,
        t.get("description") or "",
    ]

    text = " ".join(" ".join(parts).split())
    meta = {
        "owner": owner,
        "repo_name": name,
        "tool_id": t.get("tool_id"),
        "version": t.get("version"),
        "guid": t.get("guid"),
    }
    return text, meta


def build_all_docs(data):
    texts, metas = [], []
    for entry in data:
        owner, repo_name = entry["owner"], entry["name"]
        for t in entry.get("tools", []):
            txt, m = build_doc(owner, repo_name, t)
            if txt:
                texts.append(txt)
                metas.append(m)
    return texts, metas


def search_store_for_hits(description, vector_store, k=10):
    """
    Collects candidate Galaxy tools for every step of the description.

    The description is a ';'-separated list of workflow steps. Returns the
    union of the top-k hits over all steps, de-duplicated by tool guid and
    keeping the order in which the steps were retrieved.
    """
    steps = [s.strip() for s in description.split(";") if s.strip()]

    hits = []
    seen = set()
    for step in steps:
        for hit in vector_store.search(step, k=k):
            meta = hit.get("meta") or {}
            key = meta.get("guid") or hit.get("text")
            if key in seen:
                continue
            seen.add(key)
            hits.append(hit)

    return hits
