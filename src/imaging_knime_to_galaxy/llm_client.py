import os
from functools import lru_cache
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Required environment variable {name!r} is not set."
        )

    return value

@lru_cache()
def get_client() -> OpenAI:
    """
    Returns a singleton OpenAI client instance.

    The lru_cache ensures that the client is created only once and reused
    across the application, avoiding repeated initialization overhead.
    """
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("SCADSAI_API_KEY")
    )

    if not api_key:
        raise RuntimeError(
            "Neither 'LLM_API_KEY' nor 'SCADSAI_API_KEY' is set."
        )

    return OpenAI(
        base_url=get_required_env("LLM_SERVER"),
        api_key= api_key
    )


def prompt_scadsai_llm(message: str, model: str | None = None) -> str:
    """
    A prompt helper function that sends a message to ScaDS.AI LLM server at
    ZIH TU Dresden and returns only the text response.
    """
    # convert message in the right format if necessary
    if isinstance(message, str):
        message = [{"role": "user", "content": message}]

    client = get_client()

    selected_model = model or get_required_env("TRANSLATION_MODEL")

    response = client.chat.completions.create(
        model=selected_model,
        messages=message,
    )

    return response.choices[0].message.content
