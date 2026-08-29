from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from _schemas import EleriVerdictLoose
from prompting import SYSTEM_PROMPT


class AnthropicRunner:
    def __init__(self, model: str):
        self.model = model
        self.client = anthropic.Anthropic()

    def predict(self, messages: list[dict]) -> tuple[EleriVerdictLoose | None, dict, str | None]:
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=messages,
                output_format=EleriVerdictLoose,
            )
        except Exception as e:
            return None, {"input_tokens": 0, "output_tokens": 0}, str(e)

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return response.parsed_output, usage, None
