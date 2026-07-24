import json
import time
import csv
from pathlib import Path
from typing import Callable, Any
from imaging_knime_to_galaxy.rag_functions import search_store_for_hits
import requests
import os
from llama_index.core import Settings, StorageContext, load_index_from_storage
from openai import OpenAI as OpenAIClient
from llama_index.core.embeddings import BaseEmbedding
from llama_index.llms.openai_like import OpenAILike
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import inspect
from imaging_knime_to_galaxy.Vectorstore import VectorStore
from imaging_knime_to_galaxy.rag_functions import embed

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------

def extract_tools(result):
    """
    Galaxy MCP returns JSON as text inside result.content[0].text.
    """
    try:
        payload = json.loads(result.content[0].text)
    except (IndexError, AttributeError, json.JSONDecodeError) as exc:
        raise ValueError("Could not parse Galaxy MCP tool search result.") from exc

    return payload.get("data", [])

    
async def mcp_search_tools_by_name(query: str, max_tools: int = 5) -> list[dict]:

    server_params = StdioServerParameters(
        command="galaxy-mcp",
        args=[],
        env={
            "GALAXY_URL": os.environ["GALAXY_URL"],
            "GALAXY_API_KEY": os.environ["GALAXY_API_KEY"],
        },
    )

    results = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "search_tools_by_name",
                {"query": query},
            )

            raw_tools = extract_tools(result)

            for tool in raw_tools[:max_tools]:
                results.append({
                    "tool_id": tool.get("id"),
                    "tool_name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                })

    return results


# Create custom model instance
class CustomEmbedding(BaseEmbedding):
    client: OpenAIClient
    model: str = "Qwen/Qwen3-Embedding-4B"

    def _get_text_embedding(self, text: str) -> list[float]:
        return self.client.embeddings.create(
            model=self.model,
            input=text,
        ).data[0].embedding

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._get_text_embedding(query)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)
        

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------

DATA_FOLDER = Path("../../data").resolve()
BENCHMARK_PATH = DATA_FOLDER / "benchmark_data.json"
RESULTS_FOLDER = DATA_FOLDER / "FINAL_tool_retrieval_benchmark_results"
RESULTS_FOLDER.mkdir(parents=True, exist_ok=True)
VS_PATH = DATA_FOLDER/ "vector_stores/qwen.npz"
vector_store = VectorStore.load(VS_PATH, embed_fn=embed)

K = 5

base_url = "https://usegalaxy.eu"
api_key = os.environ.get("GALAXY_API_KEY")

# LlamaIndex Configs
client = OpenAIClient(
    base_url="https://llm.scads.ai/v1",
    api_key=os.environ["SCADSAI_API_KEY"],
)

# LLM
Settings.llm = OpenAILike(
    model="meta-llama/Llama-3.3-70B-Instruct",
    api_base="https://llm.scads.ai/v1",
    api_key=os.environ["SCADSAI_API_KEY"],
    is_chat_model=True,
)

# Embeddings
Settings.embed_model = CustomEmbedding(
    client=client,
    model="Qwen/Qwen3-Embedding-4B",
)

# Loading LlamaIndex
if os.path.exists("./../storage"):
    print("Loading Index ...")
    storage_context = StorageContext.from_defaults(persist_dir="./../storage")
    index = load_index_from_storage(storage_context)
else:
    raise FileNotFoundError("No valid Llama Index found at ./../storage")
        

# -------------------------------------------------------------------
# Loading benchmark cases
# -------------------------------------------------------------------

def load_benchmark_dataset(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# -------------------------------------------------------------------
# Normalization
# -------------------------------------------------------------------

def normalize_tool_id(tool_id: str | None) -> str | None:
    if not tool_id:
        return None

    tool_id = tool_id.strip()

    # Full ToolShed ID:
    # toolshed.g2.bx.psu.edu/repos/bgruening/sklearn_nn_classifier/sklearn_nn_classifier/1.0.11.2
    parts = tool_id.split("/")

    if tool_id.startswith("toolshed.") and len(parts) >= 2:
        return parts[-2]

    return tool_id


def compute_rank(
    retrieved_tool_ids: list[str],
    expected_tool_id: str,
) -> int | None:
    expected_norm = normalize_tool_id(expected_tool_id)

    for idx, tool_id in enumerate(retrieved_tool_ids):
        if normalize_tool_id(tool_id) == expected_norm:
            return idx + 1

    return None


def retrieve_with_vector_search(query: str, k: int = 5) -> list[dict]:
    """
    Strategy 1:
    Embedded ToolShed/Galaxy metadata + vector similarity.
    """
    hits = search_store_for_hits(query, vector_store)
    return [
        {
            "tool_id": h["meta"].get("tool_id"),
            "tool_name": h["meta"].get("name"),
            "description": h["text"],
        }
        for h in hits[:k]
    ]


def retrieve_with_galaxy_server(query: str, k: int = 5) -> list[dict]:
    """
    Strategy 2:
    Query Galaxy.eu / Galaxy server directly.
    """

    response = requests.get(f"{base_url}/api/tools",params={"q": query},headers={"x-api-key": api_key},)
    response.raise_for_status()
    tools = response.json()

    results = []

    for tool_id in tools[:k]:
        detail_response = requests.get(
            f"{base_url}/api/tools/{tool_id}",
            headers={"x-api-key": api_key},
            timeout=30,
        )
        detail_response.raise_for_status()

        detail = detail_response.json()

        results.append({
            "tool_id": detail.get("id", tool_id),
            "tool_name": detail.get("name", ""),
            "description": detail.get("description", ""),
        })

    return results


async def retrieve_with_mcp(query: str, k: int = 5) -> list[dict]:
    """
    Strategy 3:
    Query MCP tool retrieval.
    """
    tools = await mcp_search_tools_by_name(query, max_tools=k)

    return tools


def retrieve_with_llamaIndex(query: str, k: int = 5) -> list[dict]:
    """
    Strategy 4:
    Query Llama Index for tool retrieval.
    """
    #Create a query engine
    qe = index.as_query_engine(response_mode="compact")    
    
    # Ask questions
    q = f"""
    Find the {k} tools that best match the following description: {query}
    
    Return ONLY valid JSON in this format:
    [
      {{
        "tool_id": "string",
        "tool_name": "string",
        "description": "string"
      }}
    ]
    
    Do not include markdown, explanations, or any text before or after the JSON.
        """
    ans = qe.query(q)
    text = str(ans).strip()
    results = json.loads(text)

    if not isinstance(results, list):
        raise ValueError("LlamaIndex did not return a JSON list.")

    return results


# -------------------------------------------------------------------
# Evaluation
# -------------------------------------------------------------------

def evaluate_strategy(
    name: str,
    retrieve_fn: Callable[[str, int], list[dict]],
    benchmark_cases: list[dict],
    k: int = 5,
) -> tuple[dict, list[dict]]:

    detailed_results = []

    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_5 = 0
    reciprocal_ranks = []

    total_latency = 0.0
    failures = 0

    for case in benchmark_cases:
        case_id = case.get("id")
        query = case["query"]
        expected_tool_id = case["expected_tool_id"]

        started = time.perf_counter()

        try:
            #retrieved_tools = retrieve_fn(query, k)
            retrieved_tools = asyncio.run(retrieve_fn(query, k)) if inspect.iscoroutinefunction(retrieve_fn) else retrieve_fn(query, k)
            latency_ms = (time.perf_counter() - started) * 1000
            total_latency += latency_ms

            retrieved_tool_ids = [
                tool.get("tool_id")
                for tool in retrieved_tools[:k]
            ]

            rank = compute_rank(
                retrieved_tool_ids,
                expected_tool_id,
            )

            error = None

        except Exception as e:
            latency_ms = (time.perf_counter() - started) * 1000
            total_latency += latency_ms

            retrieved_tools = []
            retrieved_tool_ids = []
            rank = None
            error = repr(e)
            failures += 1

        if rank == 1:
            hit_at_1 += 1

        if rank is not None and rank <= 3:
            hit_at_3 += 1

        if rank is not None and rank <= 5:
            hit_at_5 += 1

        reciprocal_ranks.append(
            1 / rank if rank is not None else 0
        )

        detailed_results.append({
            "strategy": name,
            "case_id": case_id,
            "query": query,
            "expected_tool_id": expected_tool_id,
            "expected_tool_normalized": normalize_tool_id(expected_tool_id),
            "retrieved_tool_ids": retrieved_tool_ids,
            "retrieved_tool_ids_normalized": [
                normalize_tool_id(t) for t in retrieved_tool_ids
            ],
            "retrieved_tools": retrieved_tools,
            "rank": rank,
            "hit_at_1": rank == 1,
            "hit_at_3": rank is not None and rank <= 3,
            "hit_at_5": rank is not None and rank <= 5,
            "latency_ms": latency_ms,
            "error": error,
        })

    n = len(benchmark_cases)

    metrics = {
        "strategy": name,
        "N": n,
        "Recall@1": hit_at_1 / n if n else 0,
        "Recall@3": hit_at_3 / n if n else 0,
        "Recall@5": hit_at_5 / n if n else 0,
        "MRR": sum(reciprocal_ranks) / n if n else 0,
        "FailureRate": failures / n if n else 0,
        "AvgLatencyMs": total_latency / n if n else 0,
    }

    return metrics, detailed_results


# -------------------------------------------------------------------
# Saving
# -------------------------------------------------------------------

def save_json(path: Path, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_jsonl(path: Path, rows: list[dict]):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def save_summary_csv(path: Path, rows: list[dict]):
    fieldnames = [
        "strategy",
        "N",
        "Recall@1",
        "Recall@3",
        "Recall@5",
        "MRR",
        "FailureRate",
        "AvgLatencyMs",
    ]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


# -------------------------------------------------------------------
# Main benchmark
# -------------------------------------------------------------------

def run_benchmark():
    benchmark_cases = load_benchmark_dataset(BENCHMARK_PATH)

    strategies = {
        "vector_search_toolshed_metadata": retrieve_with_vector_search,
        "galaxy_server_direct": retrieve_with_galaxy_server,
        "mcp_tool_retrieval": retrieve_with_mcp,
        "LlamaIndex": retrieve_with_llamaIndex,
    }

    summary = []
    all_detailed = []

    for strategy_name, retrieve_fn in strategies.items():
        print(f"\nRunning strategy: {strategy_name}")

        metrics, detailed = evaluate_strategy(
            name=strategy_name,
            retrieve_fn=retrieve_fn,
            benchmark_cases=benchmark_cases,
            k=K,
        )

        summary.append(metrics)
        all_detailed.extend(detailed)

        save_jsonl(
            RESULTS_FOLDER / f"{strategy_name}_details.jsonl",
            detailed,
        )

        print(
            f"{strategy_name}: "
            f"R@1={metrics['Recall@1']:.3f}, "
            f"R@3={metrics['Recall@3']:.3f}, "
            f"R@5={metrics['Recall@5']:.3f}, "
            f"MRR={metrics['MRR']:.3f}, "
            f"fail={metrics['FailureRate']:.3f}, "
            f"lat={metrics['AvgLatencyMs']:.1f}ms"
        )

    save_json(
        RESULTS_FOLDER / "summary.json",
        summary,
    )

    save_summary_csv(
        RESULTS_FOLDER / "summary.csv",
        summary,
    )

    save_jsonl(
        RESULTS_FOLDER / "all_details.jsonl",
        all_detailed,
    )

    return summary, all_detailed


if __name__ == "__main__":
    run_benchmark()