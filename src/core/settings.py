import os
from dotenv import load_dotenv

from typing import Any

# Load environment variables for provider selection
load_dotenv()


# Provider component imports are optional; we import what is available and
# raise clear errors when a requested provider is not installed.
try:
    from haystack_integrations.components.generators.ollama import (
        OllamaChatGenerator,
    )
    from haystack_integrations.components.embedders.ollama import (
        OllamaTextEmbedder,
    )
    from haystack_integrations.components.embedders.ollama.document_embedder import (
        OllamaDocumentEmbedder,
    )
except Exception:
    OllamaChatGenerator = OllamaTextEmbedder = OllamaDocumentEmbedder = None

try:
    from haystack.components.generators import OpenAIChatGenerator, OpenAIGenerator
    from haystack.components.embedders import OpenAITextEmbedder, OpenAIDocumentEmbedder
except Exception:
    OpenAIChatGenerator = OpenAIGenerator = OpenAITextEmbedder = OpenAIDocumentEmbedder = None


def _env_provider_settings() -> tuple[str, str]:
    """Return the configured providers for chat and embeddings.

    Values are normalized to lowercase. Embedding provider defaults to
    the chat provider when not explicitly set.
    """
    chat = os.getenv("LLM_CHAT_PROVIDER", "ollama").lower()
    embed = os.getenv("LLM_EMBEDDING_PROVIDER", chat).lower()
    return chat, embed


def create_llm_generator(provider: str | None = None) -> Any:
    """Create and return a chat generator instance for the given provider.

    The returned object is a Haystack generator component (e.g. OllamaChatGenerator
    or OpenAIChatGenerator/OpenAIGenerator). Raises ImportError if the
    requested provider's integration is not available.
    """
    provider = (provider or _env_provider_settings()[0]).lower()
    if provider == "openai":
        if OpenAIChatGenerator is not None:
            return OpenAIChatGenerator(model=os.getenv("LLM_CHAT_MODEL"), api_key=os.getenv("OPENAI_API_KEY"))
        if OpenAIGenerator is not None:
            return OpenAIGenerator(model=os.getenv("LLM_CHAT_MODEL"), api_key=os.getenv("OPENAI_API_KEY"))
        raise ImportError("OpenAI generator components are not available. Install haystack with OpenAI support.")
    else:
        if OllamaChatGenerator is None:
            raise ImportError("Ollama chat generator is not available. Install haystack-integrations with Ollama support.")
        return OllamaChatGenerator(model=os.getenv("LLM_CHAT_MODEL"), url=os.getenv("LLM_HOST"))


def create_text_embedder(provider: str | None = None) -> Any:
    """Create and return a text embedder instance for the given provider.

    This is intended for query embeddings.
    """
    provider = (provider or _env_provider_settings()[1]).lower()
    if provider == "openai":
        if OpenAITextEmbedder is None:
            raise ImportError("OpenAI text embedder is not available. Install haystack with OpenAI support.")
        return OpenAITextEmbedder(model=os.getenv("LLM_EMBEDDING_MODEL"), api_key=os.getenv("OPENAI_API_KEY"))
    else:
        if OllamaTextEmbedder is None:
            raise ImportError("Ollama text embedder is not available. Install haystack-integrations with Ollama support.")
        return OllamaTextEmbedder(model=os.getenv("LLM_EMBEDDING_MODEL"), url=os.getenv("LLM_HOST"))


def create_document_embedder(provider: str | None = None) -> Any:
    """Create and return a document embedder for indexing.

    This is intended to be passed to the indexing pipeline.
    """
    provider = (provider or _env_provider_settings()[1]).lower()
    if provider == "openai":
        if OpenAIDocumentEmbedder is None:
            raise ImportError("OpenAI document embedder is not available. Install haystack with OpenAI support.")
        return OpenAIDocumentEmbedder(model=os.getenv("LLM_EMBEDDING_MODEL"), api_key=os.getenv("OPENAI_API_KEY"))
    else:
        if OllamaDocumentEmbedder is None:
            raise ImportError("Ollama document embedder is not available. Install haystack-integrations with Ollama support.")
        return OllamaDocumentEmbedder(model=os.getenv("LLM_EMBEDDING_MODEL"), url=os.getenv("LLM_HOST"))
