from llm_client import get_client

def embed(text: str) -> list[float]:
    """
    Creates an embedding vector for the given text.

    Returns an empty list for empty or whitespace-only input.
    Uses the shared OpenAI client instance from get_client().
    """

    if not text or not text.strip():
        return []
    client = get_client()
    response = client.embeddings.create(input=[text], model="Qwen/Qwen3-Embedding-4B")
    return response.data[0].embedding

def build_doc(owner, name, t):
    parts = [
        t.get("name") or name,
        t.get("description") or "",
        t.get("repo_description") or "",
        t.get("repo_long_description") or "",
        t.get("detailed_description_generated") or ""
    ]
    # knappe, saubere Repräsentation
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

