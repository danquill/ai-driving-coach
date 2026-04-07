"""Claude API client service for generating coaching insights.

Uses the Anthropic Python SDK with tool use to get structured JSON output.
"""

from __future__ import annotations

import structlog
import anthropic

logger = structlog.get_logger(__name__)

# Tool schema for structured coaching insights output
_COACHING_TOOL_SCHEMA = {
    "name": "record_coaching_insights",
    "description": (
        "Record structured coaching insights derived from telemetry analysis. "
        "Call this tool with all insights identified from the session data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "insights": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": [
                                "braking",
                                "corner_entry",
                                "corner_exit",
                                "sector",
                                "general",
                            ],
                        },
                        "insight_text": {"type": "string"},
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                        "distance_m_start": {
                            "type": "number",
                            "description": "Start of the relevant track segment in metres from lap start (lap-relative, not session-cumulative).",
                        },
                        "distance_m_end": {
                            "type": "number",
                            "description": "End of the relevant track segment in metres from lap start (lap-relative, not session-cumulative). Should span roughly 50–400m depending on the issue.",
                        },
                    },
                    "required": ["category", "insight_text", "confidence"],
                },
            }
        },
        "required": ["insights"],
    },
}


class ClaudeClient:
    """Thin wrapper around the Anthropic messages API for coaching insights."""

    def __init__(self, api_key: str) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-6"

    def generate_coaching_insights(
        self,
        prompt_data: dict,
    ) -> tuple[list[dict], int, int]:
        """Call Claude to generate structured coaching insights.

        Args:
            prompt_data: dict with keys "system" (str) and "user" (str).

        Returns:
            (insights_list, prompt_tokens, completion_tokens)
            insights_list: list of dicts with keys:
                category, insight_text, confidence,
                distance_m_start (optional), distance_m_end (optional)
        """
        system_prompt: str = prompt_data["system"]
        user_prompt: str = prompt_data["user"]

        logger.info("claude_client_calling_api", model=self.model)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[_COACHING_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "record_coaching_insights"},
        )

        prompt_tokens: int = response.usage.input_tokens
        completion_tokens: int = response.usage.output_tokens

        logger.info(
            "claude_client_response_received",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        # Extract the tool-use block from the response
        tool_use_block = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "record_coaching_insights":
                tool_use_block = block
                break

        if tool_use_block is None:
            logger.error("claude_client_no_tool_use_block", content=str(response.content))
            raise ValueError("Claude did not return a record_coaching_insights tool use block")

        insights: list[dict] = tool_use_block.input.get("insights", [])

        logger.info("claude_client_insights_parsed", count=len(insights))
        return insights, prompt_tokens, completion_tokens
