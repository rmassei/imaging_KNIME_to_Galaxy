import json
import csv
import time
from pathlib import Path
from difflib import SequenceMatcher

from imaging_knime_to_galaxy.Vectorstore import VectorStore
from imaging_knime_to_galaxy.rag_functions import search_store_for_hits, embed
from imaging_knime_to_galaxy.llm_client import get_client


# --------------------------------------------------
# Config
# --------------------------------------------------
N_RUNS = 5

DATA_FOLDER = Path("../../data").resolve()
BENCHMARK_PATH = DATA_FOLDER / "benchmark_data.json"
STORES_FOLDER = DATA_FOLDER / "vector_stores"
RESULTS_FOLDER = DATA_FOLDER / f"FINAL_llm_benchmark_results_runs={N_RUNS}"

RESULTS_FOLDER.mkdir(parents=True, exist_ok=True)

VECTOR_STORE_PATH = STORES_FOLDER / "qwen.npz"  
TOP_K = 5

LLM_MODELS = {
    "llama": "meta-llama/Llama-3.3-70B-Instruct",
    "gpt": "openai/gpt-oss-120b",
    "gemma": "google/gemma-4-31B-it",
}


# --------------------------------------------------
# Data loading
# --------------------------------------------------

def load_benchmark_dataset(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------
# LLM callls
    
# --------------------------------------------------

def call_llm(model_name, prompt):
    client = get_client()

    start = time.perf_counter()

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a skilled RAG assistant. "
                    "Answer only using the provided context. "
                    "If the context does not contain the answer, say: "
                    "'I don't know based on the provided context.'"
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
    )

    latency_ms = (time.perf_counter() - start) * 1000

    answer = response.choices[0].message.content.strip()

    return answer, latency_ms


# --------------------------------------------------
# Prompt building
# --------------------------------------------------

def build_rag_prompt(query, retrieved_hits):
    context_blocks = []

    for i, hit in enumerate(retrieved_hits, start=1):
        meta = hit.get("meta") or {}

        tool_id = meta.get("tool_id", "unknown")
        tool_name = (
            meta.get("name")
            or meta.get("tool_name")
            or meta.get("tool")
            or tool_id
        )

        context_blocks.append(
            f"[Tool {i}]\n"
            f"tool_name: {tool_name}\n"
            f"tool_id: {tool_id}\n"
            f"description:\n{hit['text']}"
        )

    context = "\n\n".join(context_blocks)

    return f"""
You are selecting the best matching Galaxy/KNIME tool.

User query:
{query}

Candidate tools:
{context}

Choose exactly one candidate tool from the list.

Return JSON only, with this schema:
{{
  "selected_tool_name": "...",
  "selected_tool_id": "...",
  "reason": "..."
}}

Rules:
- selected_tool_name must be copied from one of the candidate tool_name values.
- selected_tool_id must be copied from one of the candidate tool_id values.
- Do not invent a tool.
- No not answer in markdown or any unknown format. Just VALID Json.
""".strip()

# --------------------------------------------------
# Simple automatic metrics
# --------------------------------------------------

    
def normalize_text(text):
    if not text:
        return ""

    return " ".join(
        text.lower()
        .replace("\n", " ")
        .replace(".", "")
        .replace(",", "")
        .replace("_", "")
        .split()
    )


def exact_match(prediction, expected):
    return normalize_text(prediction) == normalize_text(expected)


def contains_expected(prediction, expected):
    return normalize_text(expected) in normalize_text(prediction)


def similarity_score(prediction, expected):
    return SequenceMatcher(
        None,
        normalize_text(prediction),
        normalize_text(expected),
    ).ratio()


def evaluate_answer(prediction, expected_answer):
    if not expected_answer:
        return {
            "exact_match": None,
            "contains_expected": None,
            "similarity": None,
        }

    return {
        "exact_match": exact_match(prediction, expected_answer),
        "contains_expected": contains_expected(prediction, expected_answer),
        "similarity": similarity_score(prediction, expected_answer),
    }


def parse_llm_tool_selection(answer):
    try:
        data = json.loads(answer)
        return {
            "generated_tool_name": data.get("selected_tool_name"),
            "generated_tool_id": data.get("selected_tool_id"),
            "generated_reason": data.get("reason"),
            "raw_answer": answer,
            "parse_ok": True,
        }
    except Exception:
        return {
            "generated_tool_name": None,
            "generated_tool_id": None,
            "generated_reason": None,
            "raw_answer": answer,
            "parse_ok": False,
        }

# --------------------------------------------------
# Benchmark
# --------------------------------------------------

def benchmark_llm(
    llm_label,
    llm_model_name,
    vector_store,
    benchmark_cases,
    top_k=5,
    n_runs=5,
):
    detailed_results = []

    total_latency = 0
    exact_matches = 0
    contains_matches = 0
    similarities = []
    parse_ok_count = 0
    total_runs = 0

    for case in benchmark_cases:
        query = case["query"]

        expected_answer = (
            case.get("expected_tool")
            or case.get("expected_tool_id")
            or ""
        )

        # retrieve once per benchmark sample
        retrieved_hits = search_store_for_hits(
            query,
            vector_store,
        )[:top_k]

        prompt = build_rag_prompt(query, retrieved_hits)

        for run_idx in range(1, n_runs + 1):
            answer, latency_ms = call_llm(llm_model_name, prompt)
            total_latency += latency_ms
            total_runs += 1

            parsed_answer = parse_llm_tool_selection(answer)

            if parsed_answer["parse_ok"]:
                parse_ok_count += 1

            predicted_tool = (
                parsed_answer["generated_tool_name"]
                or parsed_answer["generated_tool_id"]
                or ""
            )

            auto_metrics = evaluate_answer(predicted_tool, expected_answer)

            if auto_metrics["exact_match"]:
                exact_matches += 1

            if auto_metrics["contains_expected"]:
                contains_matches += 1

            if auto_metrics["similarity"] is not None:
                similarities.append(auto_metrics["similarity"])

            detailed_results.append({
                "case_id": case.get("id"),
                "run_idx": run_idx,
                "query": query,

                "expected_tool": case.get("expected_tool"),
                "expected_tool_id": case.get("expected_tool_id"),

                "generated_tool_name": parsed_answer["generated_tool_name"],
                "generated_tool_id": parsed_answer["generated_tool_id"],
                "generated_reason": parsed_answer["generated_reason"],
                "parse_ok": parsed_answer["parse_ok"],
                "raw_answer": parsed_answer["raw_answer"],

                "latency_ms": latency_ms,

                "retrieved_tools": [
                    {
                        "rank": i + 1,
                        "tool_id": (hit.get("meta") or {}).get("tool_id"),
                        "tool_name": (
                            (hit.get("meta") or {}).get("name")
                            or (hit.get("meta") or {}).get("tool_name")
                            or (hit.get("meta") or {}).get("tool")
                        ),
                    }
                    for i, hit in enumerate(retrieved_hits)
                ],

                "retrieved_tool_ids": [
                    (hit.get("meta") or {}).get("tool_id")
                    for hit in retrieved_hits
                ],

                "auto_metrics": auto_metrics,
            })

    n_cases = len(benchmark_cases)

    summary = {
        "model": llm_label,
        "N_cases": n_cases,
        "N_runs_per_case": n_runs,
        "N_total_runs": total_runs,
        "exact_match": exact_matches / total_runs if total_runs else 0,
        "contains_expected": contains_matches / total_runs if total_runs else 0,
        "parse_ok_rate": parse_ok_count / total_runs if total_runs else 0,
        "avg_similarity": sum(similarities) / len(similarities) if similarities else None,
        "avg_latency_ms": total_latency / total_runs if total_runs else None,
    }

    return summary, detailed_results


# --------------------------------------------------
# Saving
# --------------------------------------------------

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_summary_csv(path, summaries):
    fieldnames = sorted({
        key
        for summary in summaries.values()
        for key in summary.keys()
    })

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for _, summary in summaries.items():
            writer.writerow(summary)


# --------------------------------------------------
# Runner
# --------------------------------------------------

def benchmark_all_llms(
    llm_models,
    vector_store,
    benchmark_cases,
    top_k=5,
):
    summaries = {}

    for llm_label, llm_model_name in llm_models.items():
        print(f"\nRunning LLM benchmark for {llm_label}")

        summary, detailed = benchmark_llm(
            llm_label=llm_label,
            llm_model_name=llm_model_name,
            vector_store=vector_store,
            benchmark_cases=benchmark_cases,
            top_k=top_k,
            n_runs=N_RUNS,
        )

        summaries[llm_label] = summary

        save_json(
            RESULTS_FOLDER / f"llm_results_{llm_label}.json",
            detailed,
        )

    save_json(
        RESULTS_FOLDER / "llm_summary.json",
        summaries,
    )

    save_summary_csv(
        RESULTS_FOLDER / "llm_summary.csv",
        summaries,
    )

    return summaries


def print_summary(summaries):
    print("\n")
    print("=" * 80)
    print("LLM BENCHMARK")
    print("=" * 80)

    for model, metrics in summaries.items():
        print(f"\n{model}")
        print(f"N:                  {metrics['N_cases']}")
        print(f"Exact Match:        {metrics['exact_match']:.1%}")
        print(f"Contains Expected:  {metrics['contains_expected']:.1%}")
        print(f"Parse OK:           {metrics['parse_ok_rate']:.1%}")

        if metrics["avg_similarity"] is not None:
            print(f"Avg Similarity:     {metrics['avg_similarity']:.3f}")

        if metrics["avg_latency_ms"] is not None:
            print(f"Avg Latency:        {metrics['avg_latency_ms']:.1f} ms")

# --------------------------------------------------
# Usage
# --------------------------------------------------

benchmark_cases = load_benchmark_dataset(BENCHMARK_PATH)

store = VectorStore.load(
    VECTOR_STORE_PATH,
    embed_fn=embed,
)

summaries = benchmark_all_llms(
    llm_models=LLM_MODELS,
    vector_store=store,
    benchmark_cases=benchmark_cases,
    top_k=TOP_K,
)

print_summary(summaries)