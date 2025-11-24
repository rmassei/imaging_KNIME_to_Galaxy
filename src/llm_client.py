import os
from functools import lru_cache
from openai import OpenAI


@lru_cache()
def get_client() -> OpenAI:
    """
    Returns a singleton OpenAI client instance.

    The lru_cache ensures that the client is created only once and reused
    across the application, avoiding repeated initialization overhead.
    """

    return OpenAI(
        base_url="https://llm.scads.ai/v1",
        api_key=os.environ.get("SCADSAI_API_KEY"),
    )


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


def prompt_scadsai_llm(message: str, model: str = "openai/gpt-oss-120b") -> str:
    """
    A prompt helper function that sends a message to ScaDS.AI LLM server at
    ZIH TU Dresden and returns only the text response.
    """
    # convert message in the right format if necessary
    if isinstance(message, str):
        message = [{"role": "user", "content": message}]

    client = get_client()

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": message}],
    )

    return response.choices[0].message.content
