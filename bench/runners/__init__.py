from .anthropic_runner import AnthropicRunner
from .openai_runner import OpenAIRunner

RUNNERS = {
    "claude-haiku-4-5": lambda: AnthropicRunner("claude-haiku-4-5"),
    "gpt-4o-mini": lambda: OpenAIRunner("gpt-4o-mini"),
}

__all__ = ["AnthropicRunner", "OpenAIRunner", "RUNNERS"]
