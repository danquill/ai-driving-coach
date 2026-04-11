"""Claude API client service for generating coaching insights.

Uses the Anthropic Python SDK.  The pipeline runs two sequential calls:

  Call 1 — ANALYSIS (plain text response):
    Receives pre-classified corner blocks; outputs structured CORNER: ... blocks
    with FINDING and DELTA IMPACT fields for each corner.

  Call 2 — COACHING (tool-use response):
    Receives the Call 1 structured analysis; outputs 2-3 driver feedback insights
    via the record_coaching_insights tool.
"""

from __future__ import annotations

import re
import structlog
import anthropic

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_ANALYSIS_SYSTEM_PROMPT = (
    "You are a telemetry analysis engine. Your only job is to classify and compare — "
    "you do not generate coaching feedback or recommendations in this step.\n\n"
    "You will receive pre-classified corner data comparing one specific lap against the "
    "theoretical fastest lap (a best-sector compilation, not a real lap). "
    "Each corner block shows 'Compare lap: Lap N (compare)' — this is the actual lap being analysed. "
    "The theoretical fastest is the reference benchmark. IDEAL LAP DELTA refers to how the "
    "compare lap performed relative to the theoretical fastest sector. "
    "Use the compare lap number when the coaching step asks for a lap reference.\n\n"
    "For each corner, output a structured analysis block using exactly this format:\n\n"
    "CORNER: [name/number]\n"
    "PHASE: [entry / turn-in / mid-corner / exit]\n"
    "FRONT AXLE STATE: [loaded / unloaded / transitioning]\n"
    "DECELERATION NEEDED: [yes / no / already complete]\n"
    "IDEAL LAP DELTA: [faster / slower / matched] by [X mph] at [phase]\n"
    "HANDLING CONDITION: [neutral / understeering / oversteering / coasting / overslowing / none]\n"
    "CONDITION PHASE: [entry / turn-in / mid-corner / exit]\n"
    "TECHNIQUE IN USE: [threshold / trail brake / brush brake / coast / none]\n"
    "TECHNIQUE CORRECT FOR PHASE: [yes / no / partially]\n"
    "FINDING: [one sentence describing what is happening and where the delta comes from]\n"
    "DELTA IMPACT: [high / medium / low]\n\n"
    "Rules for classification:\n"
    "- Threshold braking is correct only when: phase is entry AND deceleration needed is yes\n"
    "- Trail braking is correct only when: phase is entry-to-mid transition AND brake trace "
    "shows progressive reduction while steering is loading\n"
    "- Brush braking is correct when: phase is turn-in or mid-corner AND front axle is "
    "unloaded AND deceleration needed is no\n"
    "- Coast is a finding when: brake and throttle are both zero AND speed is above minimum "
    "corner speed AND the gap cannot be explained by traffic\n"
    "- DELTA IMPACT must be rated based on the average sector delta, NOT the best-lap delta. "
    "When the input labels a sector as 'ideal sector sourced from Lap N — zero delta expected', "
    "that zero refers only to the single source lap; use the average delta as your impact rating.\n"
    "- Rate DELTA IMPACT high if average sector delta > 500ms, medium if 200–500ms, low if < 200ms. "
    "When all corners are below 200ms average, still rate the worst corner medium — "
    "the coach always needs at least one actionable finding.\n"
    "- Do not rate DELTA IMPACT low solely because the best-lap delta is zero.\n\n"
    "Do not explain your classifications. Do not generate recommendations. "
    "Output structured blocks only."
)

_COACHING_SYSTEM_PROMPT = (
    "You are an elite motorsport driving coach. You will receive a structured telemetry "
    "analysis that has already classified each corner, identified handling conditions, "
    "and rated delta impact. Your job is to generate driver feedback from this analysis — "
    "you do not re-analyze the telemetry or override the classifications.\n\n"
    "LAP CONTEXT: You are analysing one specific lap against the theoretical fastest lap "
    "(a best-sector compilation from this session — not a real lap). "
    "Each corner block shows 'Compare lap: Lap N (compare)' — N is the actual lap number being analysed. "
    "The theoretical fastest is the benchmark the driver is measured against. "
    "Frame feedback as: 'On Lap N at T8, you...' contrasted with 'the theoretical fastest shows...'. "
    "N is always the number from 'Compare lap: Lap N (compare)'.\n\n"
    "FEEDBACK RULES:\n"
    "- Select the 2-3 corners with the highest DELTA IMPACT rating. "
    "If no corners are rated high, use the medium-rated corners. "
    "If all are rated low, use the worst 2 — always produce feedback.\n"
    "- Do not generate feedback for a corner only when TECHNIQUE CORRECT FOR PHASE is yes "
    "AND IDEAL LAP DELTA is matched AND average delta is under 100ms — that is the only "
    "combination that warrants skipping a corner.\n"
    "- A zero ideal lap delta caused by the source lap artefact is NOT grounds to skip a corner — "
    "use the FINDING and the average delta to determine whether feedback is warranted.\n"
    "- Each insight_text MUST open with 'On Lap X, at [corner]...' where X is the actual lap number "
    "from 'Compare lap: Lap X (compare)' in the corner data. "
    "Never write 'compare lap', 'your compare lap', 'worst lap', or any label — "
    "only the number (e.g. 'On Lap 5, at T8...').\n"
    "- Set distance_m_start and distance_m_end from the 'Analysis window' field in the corner data. "
    "These values are always present — use them directly as numbers. "
    "Do NOT write any disclaimer about distances in insight_text. "
    "Do NOT write 'UNKNOWN', 'not provided', or 'Analysis window' anywhere in insight_text.\n"
    "- For each finding, your feedback must follow this structure:\n"
    "  1. Where: reference the corner name and distance marker\n"
    "  2. What: describe what the telemetry shows is happening, contrasted against "
    "     what the driver did on their ideal lap sector\n"
    "  3. Why: explain the physics or technique principle in plain language\n"
    "  4. Fix: one concrete, actionable correction for the next session\n\n"
    "TECHNIQUE LANGUAGE RULES:\n"
    "- If the fix involves brush braking, describe it only in weight transfer terms: "
    "'a light squeeze to load the front axle' — never 'slow down' or 'scrub speed'\n"
    "- If the fix involves trail braking, describe the brake release as progressive "
    "and tied to steering load — not as 'hold the brake longer'\n"
    "- If the finding is coasting or overslowing, do not recommend harder braking — "
    "recommend moving the brake point later or building minimum speed incrementally\n\n"
    "Tone: encouraging and direct. The driver is an intelligent adult. "
    "Be specific about what is working. Avoid vague praise. "
    "Keep each insight_text under 100 words — be concise and actionable."
)

# ---------------------------------------------------------------------------
# Tool schema for Call 2 structured output
# ---------------------------------------------------------------------------

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
                        "corner_name": {
                            "type": "string",
                            "description": "The corner name this insight refers to, exactly as it appears in the 'Corner:' field of the corner data (e.g. 'T8', 'T4', 'T1').",
                        },
                        "distance_m_start": {
                            "type": "number",
                            "description": "Lap-relative distance in metres where this finding begins. Copy the start value directly from the 'Analysis window' field in the corner data.",
                        },
                        "distance_m_end": {
                            "type": "number",
                            "description": "Lap-relative distance in metres where this finding ends. Copy the end value directly from the 'Analysis window' field in the corner data.",
                        },
                    },
                    "required": ["category", "insight_text", "confidence", "corner_name", "distance_m_start", "distance_m_end"],
                },
            }
        },
        "required": ["insights"],
    },
}


def _validate_analysis_output(text: str, expected_corners: int) -> None:
    """Raise ValueError if Call 1 output is malformed.

    Checks:
    - At least one CORNER: block is present
    - Every block has a DELTA IMPACT: field
    - Total blocks >= expected_corners (the number we sent in)
    """
    corner_blocks = re.findall(r"^CORNER:", text, re.MULTILINE)
    if not corner_blocks:
        raise ValueError(
            "Call 1 (analysis) returned no CORNER: blocks — response may be malformed. "
            f"Response length: {len(text)} chars."
        )

    delta_impacts = re.findall(r"^DELTA IMPACT:", text, re.MULTILINE)
    if len(delta_impacts) < len(corner_blocks):
        raise ValueError(
            f"Call 1 (analysis) returned {len(corner_blocks)} CORNER: blocks but only "
            f"{len(delta_impacts)} DELTA IMPACT: fields — output is incomplete."
        )

    if len(corner_blocks) < expected_corners:
        raise ValueError(
            f"Call 1 (analysis) returned {len(corner_blocks)} corner blocks but "
            f"{expected_corners} corners were submitted. Output is incomplete."
        )


class ClaudeClient:
    """Thin wrapper around the Anthropic messages API for coaching insights.

    Implements a two-call pipeline:
      1. generate_telemetry_analysis() — structured corner classification (text)
      2. generate_coaching_insights() — driver feedback from the analysis (tool use)

    The public entry point generate_coaching_insights() orchestrates both calls
    and returns only the final coaching insights to the caller.
    """

    def __init__(self, api_key: str) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-6"

    def generate_telemetry_analysis(
        self,
        corner_classifications_text: str,
        expected_corners: int = 1,
    ) -> tuple[str, int, int]:
        """Call 1: classify corners and produce structured analysis blocks.

        Args:
            corner_classifications_text: pre-computed corner blocks (from
                format_corner_classifications()) including the IDEAL LAP NOTE header.
            expected_corners: number of corner blocks submitted; used for validation.

        Returns:
            (analysis_text, prompt_tokens, completion_tokens)

        Raises:
            ValueError: if the response is malformed (missing DELTA IMPACT fields or
                fewer blocks than expected_corners).
        """
        logger.info(
            "claude_client_call1_start",
            model=self.model,
            expected_corners=expected_corners,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=_ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": corner_classifications_text}],
        )

        prompt_tokens: int = response.usage.input_tokens
        completion_tokens: int = response.usage.output_tokens

        logger.info(
            "claude_client_call1_done",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        _validate_analysis_output(text, expected_corners)

        logger.debug("claude_client_call1_output", analysis_text=text[:500])
        return text, prompt_tokens, completion_tokens

    def generate_coaching_from_analysis(
        self,
        analysis_text: str,
        knowledge_constraint_text: str | None = None,
    ) -> tuple[list[dict], int, int]:
        """Call 2: generate driver feedback from Call 1 structured analysis.

        Args:
            analysis_text: full text output from generate_telemetry_analysis().
            knowledge_constraint_text: optional CORNER-SPECIFIC CONSTRAINTS block
                from format_corner_knowledge(). When provided, appended to the
                coaching system prompt as hard constraints.

        Returns:
            (insights_list, prompt_tokens, completion_tokens)
        """
        user_message = (
            "The following is the structured telemetry analysis for this session. "
            "Generate driver feedback based on this analysis only:\n\n"
            + analysis_text
        )

        system_prompt = _COACHING_SYSTEM_PROMPT
        if knowledge_constraint_text:
            system_prompt = system_prompt + "\n\n" + knowledge_constraint_text

        logger.info("claude_client_call2_start", model=self.model)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=[_COACHING_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "record_coaching_insights"},
        )

        prompt_tokens: int = response.usage.input_tokens
        completion_tokens: int = response.usage.output_tokens

        logger.info(
            "claude_client_call2_done",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            stop_reason=response.stop_reason,
        )

        tool_use_block = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "record_coaching_insights":
                tool_use_block = block
                break

        if tool_use_block is None:
            logger.error("claude_client_no_tool_use_block", content=str(response.content))
            raise ValueError("Claude did not return a record_coaching_insights tool use block")

        raw_insights = tool_use_block.input.get("insights", [])
        logger.debug(
            "claude_client_raw_insights_type",
            input_type=type(tool_use_block.input).__name__,
            insights_type=type(raw_insights).__name__,
            insights_repr=repr(raw_insights)[:200],
        )
        if isinstance(raw_insights, str):
            import json as _json
            try:
                raw_insights = _json.loads(raw_insights)
            except Exception:
                logger.error("claude_client_insights_json_parse_failed", raw=raw_insights[:200])
                raw_insights = []
        insights: list[dict] = [i for i in raw_insights if isinstance(i, dict)]
        if len(insights) < len(raw_insights):
            logger.warning(
                "claude_client_insights_filtered_non_dict",
                total=len(raw_insights),
                kept=len(insights),
            )

        logger.info("claude_client_insights_parsed", count=len(insights))
        return insights, prompt_tokens, completion_tokens

    def generate_coaching_insights(
        self,
        prompt_data: dict,
        corner_classifications_text: str | None = None,
        knowledge_constraint_text: str | None = None,
    ) -> tuple[list[dict], int, int]:
        """Orchestrate the two-call pipeline.

        If corner_classifications_text is provided, runs Call 1 → Call 2.
        If not provided, falls back to the legacy single-call path using prompt_data
        directly (preserves backward compatibility for callers that have not yet
        been updated).

        Args:
            prompt_data: dict with keys "system" (str) and "user" (str).
                Used in the legacy single-call path only.
            corner_classifications_text: pre-formatted corner classification block
                (from format_corner_classifications()). When present, drives the
                two-call pipeline.

        Returns:
            (insights_list, total_prompt_tokens, total_completion_tokens)
        """
        if corner_classifications_text is not None:
            # Two-call pipeline
            expected = corner_classifications_text.count("Corner:")
            analysis_text, p1, c1 = self.generate_telemetry_analysis(
                corner_classifications_text,
                expected_corners=max(1, expected),
            )
            logger.info("claude_client_analysis_complete", analysis_preview=analysis_text[:300])
            insights, p2, c2 = self.generate_coaching_from_analysis(
                analysis_text,
                knowledge_constraint_text=knowledge_constraint_text,
            )
            return insights, p1 + p2, c1 + c2

        # Legacy single-call path (backward compatible)
        system_prompt: str = prompt_data["system"]
        user_prompt: str = prompt_data["user"]

        logger.info("claude_client_calling_api_legacy", model=self.model)

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

        tool_use_block = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "record_coaching_insights":
                tool_use_block = block
                break

        if tool_use_block is None:
            logger.error("claude_client_no_tool_use_block", content=str(response.content))
            raise ValueError("Claude did not return a record_coaching_insights tool use block")

        raw_insights = tool_use_block.input.get("insights", [])
        if isinstance(raw_insights, str):
            import json as _json
            try:
                raw_insights = _json.loads(raw_insights)
            except Exception:
                raw_insights = []
        insights: list[dict] = [i for i in raw_insights if isinstance(i, dict)]

        logger.info("claude_client_insights_parsed", count=len(insights))
        return insights, prompt_tokens, completion_tokens
