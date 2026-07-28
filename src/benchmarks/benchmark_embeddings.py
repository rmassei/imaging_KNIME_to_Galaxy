import json
import csv
from pathlib import Path

from imaging_knime_to_galaxy.Vectorstore import VectorStore
from imaging_knime_to_galaxy.rag_functions import search_store_for_hits, build_all_docs
from imaging_knime_to_galaxy.knime_io import load_tools_metadata
from sentence_transformers import SentenceTransformer
from imaging_knime_to_galaxy.llm_client import get_client

# --------------------------------------------------
# Config
# --------------------------------------------------

DATA_FOLDER = Path("../../data").resolve()
STORES_FOLDER = DATA_FOLDER / "vector_stores"
BENCHMARK_PATH = DATA_FOLDER / "benchmark_data.json"

RESULTS_FOLDER = DATA_FOLDER / "embedding_benchmark_results"
TOOL_META_PATH=DATA_FOLDER / "tools_metadata.json"

RESULTS_FOLDER.mkdir(parents=True, exist_ok=True)
STORES_FOLDER.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Embedding Functions
# --------------------------------------------------
# ---- QWEN ----
def embed_qwen(texts):
    client = get_client()
    single_input = isinstance(texts, str)

    if single_input:
        texts = [texts]

    texts = [t if (t and t.strip()) else " " for t in texts]

    response = client.embeddings.create(
        input=texts,
        model="Qwen/Qwen3-Embedding-4B"
    )
    embeddings = [d.embedding for d in response.data]

    if single_input:
        return embeddings[0]

    return embeddings


# ---- HARRIER ----
_harrier = None

def embed_harrier(texts):
    global _harrier

    if _harrier is None:
        _harrier = SentenceTransformer(
            "microsoft/harrier-oss-v1-0.6b",
            model_kwargs={"dtype": "auto"}
        )

    return _harrier.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        normalize_embeddings=True
    )


# ---- PERPLEXITY ----
_perplexity = None

def embed_perplexity(texts):
    global _perplexity

    if _perplexity is None:
        _perplexity = SentenceTransformer(
            "perplexity-ai/pplx-embed-v1-4B",
            trust_remote_code=True
        )

    return _perplexity.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        normalize_embeddings=True
    )
    
# --------------------------------------------------
# Loading benchmark data
# --------------------------------------------------

def load_benchmark_dataset(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------
# Vector store handling
# --------------------------------------------------

def get_or_create_store(name, embed_fn, texts, metas, stores_folder):
    path = stores_folder / f"{name}.npz"

    if path.exists():
        print(f"Loading existing vector store: {path}")
        return VectorStore.load(path, embed_fn=embed_fn)

    print(f"Building new vector store: {name}")
    store = VectorStore(
        embed_fn=embed_fn,
        texts=texts,
        metadatas=metas,
    )

    print(f"Saving vector store: {path}")
    store.save(path)

    return store


def load_all_vector_stores(embedding_models, texts, metas, stores_folder):
    stores = {}

    for name, embed_fn in embedding_models.items():
        stores[name] = get_or_create_store(
            name=name,
            embed_fn=embed_fn,
            texts=texts,
            metas=metas,
            stores_folder=stores_folder,
        )

        print(
            f"{name}: "
            f"{len(stores[name].texts)} docs, "
            f"vectors={stores[name].vectors.shape}"
        )

    return stores


# --------------------------------------------------
# Metrics
# --------------------------------------------------

def normalize_tool_id(tool_id):
    if not tool_id:
        return None

    parts = tool_id.split("/")

    if len(parts) >= 2:
        return parts[-2]  

    return tool_id
    

def compute_rank(retrieved_tool_ids, expected_tool_id):
    expected_norm = normalize_tool_id(expected_tool_id)

    for idx, tool_id in enumerate(retrieved_tool_ids):
        if normalize_tool_id(tool_id) == expected_norm:
            return idx + 1

    return None


def evaluate_retrieval(vector_store, benchmark_cases, k=5):
    detailed_results = []

    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_5 = 0

    for case in benchmark_cases:
        query = case["query"]
        expected_tool_id = case["expected_tool_id"]

        hits = search_store_for_hits(query, vector_store)

        retrieved_tool_ids = [
            hit["meta"].get("tool_id")
            for hit in hits[:k]
        ]

        rank = compute_rank(
            retrieved_tool_ids,
            expected_tool_id,
        )

        if rank == 1:
            hit_at_1 += 1

        if rank is not None and rank <= 3:
            hit_at_3 += 1

        if rank is not None and rank <= 5:
            hit_at_5 += 1

        detailed_results.append({
            "case_id": case.get("id"),
            "query": query,
            "expected_tool_id": expected_tool_id,
            "retrieved_tool_ids": retrieved_tool_ids,
            "rank": rank,
            "hit_at_1": rank == 1,
            "hit_at_3": rank is not None and rank <= 3,
            "hit_at_5": rank is not None and rank <= 5,
        })

    n = len(benchmark_cases)

    metrics = {
        "N": n,
        "Recall@1": hit_at_1 / n if n else 0,
        "Recall@3": hit_at_3 / n if n else 0,
        "Recall@5": hit_at_5 / n if n else 0,
    }

    return metrics, detailed_results


# --------------------------------------------------
# Saving
# --------------------------------------------------

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_summary_csv(path, summary):
    fieldnames = [
        "model",
        "N",
        "Recall@1",
        "Recall@3",
        "Recall@5",
    ]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for model, metrics in summary.items():
            row = {"model": model}
            row.update(metrics)
            writer.writerow(row)


# --------------------------------------------------
# Benchmark runner
# --------------------------------------------------

def benchmark_all_models(
    embedding_models,
    texts,
    metas,
    benchmark_path=BENCHMARK_PATH,
    stores_folder=STORES_FOLDER,
    results_folder=RESULTS_FOLDER,
    k=5,
):
    benchmark_cases = load_benchmark_dataset(benchmark_path)

    vector_stores = load_all_vector_stores(
        embedding_models=embedding_models,
        texts=texts,
        metas=metas,
        stores_folder=stores_folder,
    )

    summary = {}

    for name, store in vector_stores.items():
        print(f"\nRunning benchmark for {name}")

        metrics, detailed = evaluate_retrieval(
            vector_store=store,
            benchmark_cases=benchmark_cases,
            k=k,
        )

        summary[name] = metrics

        save_json(
            results_folder / f"retrieval_results_{name}.json",
            detailed,
        )

    save_json(
        results_folder / "retrieval_summary.json",
        summary,
    )

    save_summary_csv(
        results_folder / "retrieval_summary.csv",
        summary,
    )

    return summary


def print_summary(summary):
    print("\n")
    print("=" * 80)
    print("EMBEDDING BENCHMARK")
    print("=" * 80)

    for model, metrics in summary.items():
        print(f"\n{model}")
        print(f"N:        {metrics['N']}")
        print(f"Recall@1: {metrics['Recall@1']:.3f}")
        print(f"Recall@3: {metrics['Recall@3']:.3f}")
        print(f"Recall@5: {metrics['Recall@5']:.3f}")


# --------------------------------------------------
# Usage
# --------------------------------------------------

meta_data = load_tools_metadata(TOOL_META_PATH)
texts, metas = build_all_docs(meta_data)
embedding_models = {
    "harrier": embed_harrier,
    "perplexity": embed_perplexity,
    "qwen": embed_qwen,
}

summary = benchmark_all_models(
    embedding_models=embedding_models,
    texts=texts,
    metas=metas,
    benchmark_path=BENCHMARK_PATH,
    stores_folder=STORES_FOLDER,
    results_folder=RESULTS_FOLDER,
    k=5,
)

print_summary(summary)