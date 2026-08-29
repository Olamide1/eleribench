from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI
from _schemas import EleriVerdictLoose
from prompting import OPENAI_VERDICT_SCHEMA, SYSTEM_PROMPT


class OpenAIRunner:
    def __init__(self, model: str):
        self.model = model
        self.client = OpenAI()

    def predict(self, messages: list[dict]) -> tuple[EleriVerdictLoose | None, dict, str | None]:
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "eleri_verdict", "strict": True, "schema": OPENAI_VERDICT_SCHEMA},
                },
            )
        except Exception as e:
            return None, {"input_tokens": 0, "output_tokens": 0}, str(e)

        usage = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        }
        content = response.choices[0].message.content
        try:
            parsed = EleriVerdictLoose.model_validate(json.loads(content))
        except Exception as e:
            return None, usage, f"validation error: {e}; raw={content!r}"

        return parsed, usage, None
