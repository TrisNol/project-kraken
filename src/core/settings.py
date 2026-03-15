from typing import Any

from haystack.utils import Secret

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
    from haystack.components.generators.chat import OpenAIChatGenerator
    from haystack.components.embedders import OpenAITextEmbedder, OpenAIDocumentEmbedder
except Exception:
    OpenAIChatGenerator = OpenAITextEmbedder = (
        OpenAIDocumentEmbedder
    ) = None

def create_llm_generator(
    provider: str,
    model: str | None,
    host: str | None,
    openai_api_key: str | None,
) -> Any:
    """Create and return a chat generator instance for the given provider.

    The returned object is a Haystack generator component (e.g. OllamaChatGenerator
    or OpenAIChatGenerator/OpenAIGenerator). Raises ImportError if the
    requested provider's integration is not available.
    """
    provider = provider.lower()
    if provider == "openai":
        if OpenAIChatGenerator is not None:
            return OpenAIChatGenerator(
                model=model,
                api_key=Secret.from_token(openai_api_key),
            )
        raise ImportError(
            "OpenAI chat generator is not available. Install haystack with OpenAI support."
        )
    else:
        if OllamaChatGenerator is None:
            raise ImportError(
                "Ollama chat generator is not available. Install haystack-integrations with Ollama support."
            )
        return OllamaChatGenerator(model=model, url=host)


def create_text_embedder(
    provider: str,
    model: str | None,
    host: str | None,
    openai_api_key: str | None,
    embedding_dimension: int,
) -> Any:
    """Create and return a text embedder instance for the given provider.

    This is intended for query embeddings.
    """
    provider = provider.lower()
    if provider == "openai":
        if OpenAITextEmbedder is None:
            raise ImportError(
                "OpenAI text embedder is not available. Install haystack with OpenAI support."
            )
        return OpenAITextEmbedder(
            model=model,
            api_key=Secret.from_token(openai_api_key),
            dimensions=embedding_dimension,
        )
    else:
        if OllamaTextEmbedder is None:
            raise ImportError(
                "Ollama text embedder is not available. Install haystack-integrations with Ollama support."
            )
        return OllamaTextEmbedder(model=model, url=host)


def create_document_embedder(
    provider: str,
    model: str | None,
    host: str | None,
    openai_api_key: str | None,
    embedding_dimension: int,
) -> Any:
    """Create and return a document embedder for indexing.

    This is intended to be passed to the indexing pipeline.
    """
    provider = provider.lower()
    if provider == "openai":
        if OpenAIDocumentEmbedder is None:
            raise ImportError(
                "OpenAI document embedder is not available. Install haystack with OpenAI support."
            )
        return OpenAIDocumentEmbedder(
            model=model,
            api_key=Secret.from_token(openai_api_key),
            dimensions=embedding_dimension,
        )
    else:
        if OllamaDocumentEmbedder is None:
            raise ImportError(
                "Ollama document embedder is not available. Install haystack-integrations with Ollama support."
            )
        return OllamaDocumentEmbedder(model=model, url=host)
