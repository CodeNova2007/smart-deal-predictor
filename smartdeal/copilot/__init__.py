"""Grounded shopping copilot."""

from .local_answers import QUICK_PROMPTS, answer_locally, detect_intent
from .openrouter import ModelResult, OpenRouterClient
from .service import CopilotAnswer, ask_copilot

__all__ = [
    "QUICK_PROMPTS",
    "CopilotAnswer",
    "ModelResult",
    "OpenRouterClient",
    "answer_locally",
    "ask_copilot",
    "detect_intent",
]
