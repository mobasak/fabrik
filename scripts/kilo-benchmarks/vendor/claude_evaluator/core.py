"""Claude Code CLI evaluator — structured AI evaluation for any domain.

Calls `npx @anthropic-ai/claude-code --print` as a subprocess.
Free via Claude Code subscription. No API key needed.

Two modes:
1. Batch evaluation: score a list of items → get JSON array back
2. Text evaluation: send a single text/document → get JSON object back

Usage (batch):
    from claude_evaluator import ClaudeEvaluator, EvalConfig

    config = EvalConfig(
        system_prompt="You are an expert. Return ONLY valid JSON.",
        user_prompt_template="Score these: {items}",
    )
    evaluator = ClaudeEvaluator(config)
    results = await evaluator.evaluate(items)

Usage (single text):
    result = await evaluator.evaluate_text(
        "Review this article for accuracy and bias:\\n\\n" + article_text
    )

Usage (sync):
    results = evaluator.evaluate_sync(items)
    result = evaluator.evaluate_text_sync("Review this: ...")
"""

import asyncio
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class EvalConfig:
    """Configuration for Claude evaluator."""

    system_prompt: str
    user_prompt_template: str = "{items}"  # must contain {items} for batch mode
    model: str = "opus"
    batch_size: int = 50
    timeout: int = 300
    id_field: str = "id"
    confidence_field: str | None = "confidence"
    confidence_threshold: int = 3
    metadata_separator: str = " | "
    on_error: Callable[[str, Exception | None], None] | None = None
    # Working / scratch dir for the CLI subprocess. None = resolve at call
    # time from CLAUDE_EVALUATOR_TMPDIR, then TMPDIR, then the platform temp
    # dir. Never hardcode /tmp so the module runs unmodified on any host.
    work_dir: str | None = None


@dataclass
class EvalResult:
    """Result of evaluating a batch of items."""

    scored: dict[str, dict] = field(default_factory=dict)
    abstained: dict[str, dict] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)


class ClaudeEvaluator:
    """Evaluates items or text using Claude Code CLI."""

    def __init__(self, config: EvalConfig):
        self.config = config

    # ── Batch evaluation (list of items → JSON array) ────────────────

    async def evaluate(self, items: list[dict], extra_prompt: str = "") -> EvalResult:
        """Evaluate a list of items. Returns EvalResult with scored/abstained/failed."""
        result = EvalResult()
        if not items:
            return result

        for i in range(0, len(items), self.config.batch_size):
            batch = items[i : i + self.config.batch_size]
            batch_result = await self._evaluate_batch(batch, extra_prompt)

            for item_id, scores in batch_result.items():
                if self._is_abstained(scores):
                    result.abstained[item_id] = scores
                else:
                    result.scored[item_id] = scores

            scored_ids = set(batch_result.keys())
            for pos, item in enumerate(batch):
                item_id = str(item.get(self.config.id_field, ""))
                if not item_id:
                    # An item with a missing/empty id_field can never be
                    # matched back to a model result. Surface it in `failed`
                    # with a synthetic, collision-free marker rather than
                    # letting it vanish from every bucket (CLAUDE.md: "no
                    # silent failures"). The marker encodes the global index
                    # so it never clashes with a real id.
                    result.failed.append(f"__missing_id__:{i + pos}")
                elif item_id not in scored_ids:
                    result.failed.append(item_id)

        return result

    def evaluate_sync(self, items: list[dict], extra_prompt: str = "") -> EvalResult:
        """Synchronous version of evaluate()."""
        return asyncio.run(self.evaluate(items, extra_prompt))

    # ── Single text evaluation (one text → JSON object) ──────────────

    async def evaluate_text(self, prompt: str) -> dict:
        """Send a single prompt (can be long text) and get a JSON response.

        Use for: reviewing a document, analyzing code, evaluating a single item
        with its full content rather than a metadata summary.
        """
        try:
            raw = await asyncio.to_thread(self._call_cli, prompt)
            return self._parse_single(raw)
        except subprocess.TimeoutExpired:
            self._handle_error("evaluate_text_timeout", None)
            return {}
        except Exception as e:
            self._handle_error("evaluate_text_failed", e)
            return {}

    def evaluate_text_sync(self, prompt: str) -> dict:
        """Synchronous version of evaluate_text()."""
        return asyncio.run(self.evaluate_text(prompt))

    # ── Raw call (full control) ──────────────────────────────────────

    async def call_raw(self, prompt: str) -> str:
        """Send a prompt and get raw string response. No JSON parsing.

        Use when you need Claude's output as-is (prose, markdown, etc.)
        """
        try:
            return await asyncio.to_thread(self._call_cli, prompt)
        except Exception as e:
            self._handle_error("call_raw_failed", e)
            return ""

    def call_raw_sync(self, prompt: str) -> str:
        """Synchronous version of call_raw()."""
        return asyncio.run(self.call_raw(prompt))

    # ── Internal ─────────────────────────────────────────────────────

    async def _evaluate_batch(self, batch: list[dict], extra_prompt: str) -> dict[str, dict]:
        """Evaluate a single batch of items."""
        items_text = self._format_items(batch)
        prompt = self.config.user_prompt_template.format(items=items_text)
        if extra_prompt:
            prompt += "\n\n" + extra_prompt

        try:
            raw = await asyncio.to_thread(self._call_cli, prompt)
            return self._parse_response(raw)
        except subprocess.TimeoutExpired:
            self._handle_error("batch_timeout", None)
            return {}
        except Exception as e:
            self._handle_error("batch_failed", e)
            return {}

    def _resolve_work_dir(self) -> str:
        """Resolve the scratch/working dir for the subprocess.

        Order: explicit config.work_dir -> CLAUDE_EVALUATOR_TMPDIR ->
        TMPDIR -> platform default (``tempfile.gettempdir()``). Never
        hardcoded to ``/tmp`` so the module runs unmodified on WSL, in
        Docker, and on read-only / non-Linux hosts.
        """
        work_dir = (
            self.config.work_dir or os.getenv("CLAUDE_EVALUATOR_TMPDIR") or tempfile.gettempdir()
        )
        os.makedirs(work_dir, exist_ok=True)
        return work_dir

    def _call_cli(self, prompt: str) -> str:
        """Call Claude Code CLI with prompt via temp file + stdin."""
        work_dir = self._resolve_work_dir()
        fd, prompt_path = tempfile.mkstemp(suffix=".txt", dir=work_dir)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(prompt)

            with open(prompt_path) as stdin_file:
                result = subprocess.run(
                    [
                        "npx",
                        "@anthropic-ai/claude-code",
                        "--print",
                        "--output-format",
                        "text",
                        "--model",
                        self.config.model,
                        "--system-prompt",
                        self.config.system_prompt,
                    ],
                    stdin=stdin_file,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout,
                    cwd=work_dir,
                )
            if result.returncode != 0:
                # Fail closed: a non-zero exit (auth failure, unknown model,
                # npx not found) must surface as an error, not be swallowed
                # as an empty/garbage response that parses to {}.
                raise RuntimeError(
                    f"claude-code CLI exited {result.returncode}: "
                    f"{(result.stderr or '').strip()[:500]}"
                )
            return result.stdout
        finally:
            os.unlink(prompt_path)

    def _format_items(self, items: list[dict]) -> str:
        """Format items with metadata for the prompt.

        Each item becomes: item-id | key1=val1 | key2=val2
        """
        lines = []
        sep = self.config.metadata_separator
        id_field = self.config.id_field

        for item in items:
            item_id = str(item.get(id_field, ""))
            parts = [item_id]
            for k, v in item.items():
                if k == id_field or v is None:
                    continue
                parts.append(f"{k}={v}")
            lines.append(sep.join(parts))

        return "\n".join(lines)

    def _parse_response(self, raw: str) -> dict[str, dict]:
        """Parse Claude's JSON array response. Handles markdown fences."""
        parsed = self._extract_json(raw)
        if isinstance(parsed, list):
            return self._index_results(parsed)
        if isinstance(parsed, dict):
            return self._index_results([parsed])
        return {}

    def _parse_single(self, raw: str) -> dict:
        """Parse Claude's JSON object response for single text evaluation."""
        parsed = self._extract_json(raw)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed[0] if isinstance(parsed[0], dict) else {}
        return {}

    def _extract_json(self, raw: str):
        """Extract JSON from raw response, handling markdown fences and surrounding text.

        Uses a balanced-fragment scanner (``json.JSONDecoder.raw_decode``)
        rather than a greedy ``find("[") .. rfind("]")`` slice. A greedy
        slice breaks when the model emits prose containing a stray bracket
        before the real payload — e.g. ``"Here are results [see below]:\\n
        [{...}]"`` — collapsing a whole batch array into the first object
        it can find. The scanner instead walks each candidate ``[`` / ``{``
        start position and returns the first one that decodes to a complete
        JSON value, so a batch array survives surrounding chatter.
        """
        text = raw.strip()

        # Strip markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            text = "\n".join(lines).strip()

        # Try direct parse (fast path for clean JSON).
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Prefer an array (batch shape); fall back to an object. Scanning
        # both in this order means a stray '[' in prose can't shadow the
        # real array, and a stray array can't shadow a single object when
        # no array is actually present.
        array = self._scan_first_json(text, "[")
        if array is not None:
            return array
        return self._scan_first_json(text, "{")

    @staticmethod
    def _scan_first_json(text: str, opener: str):
        """Return the first balanced JSON value of ``opener`` type in ``text``.

        Walks every occurrence of ``opener`` ('[' or '{') and attempts a
        ``raw_decode`` there, returning the first that yields a complete
        value of the matching container type. Stray/unbalanced brackets in
        surrounding prose are skipped instead of corrupting the slice.
        """
        decoder = json.JSONDecoder()
        want_type = list if opener == "[" else dict
        idx = text.find(opener)
        while idx != -1:
            try:
                value, _ = decoder.raw_decode(text, idx)
            except json.JSONDecodeError:
                idx = text.find(opener, idx + 1)
                continue
            if isinstance(value, want_type):
                return value
            idx = text.find(opener, idx + 1)
        return None

    def _index_results(self, data: list) -> dict[str, dict]:
        """Convert list of dicts to {id: dict} map."""
        result = {}
        id_field = self.config.id_field
        for item in data:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get(id_field, ""))
            if item_id:
                result[item_id] = item
        return result

    def _is_abstained(self, scores: dict) -> bool:
        """Check if Claude abstained on this item (confidence below threshold)."""
        if not self.config.confidence_field:
            return False
        confidence = scores.get(self.config.confidence_field)
        if confidence is None:
            return True
        try:
            return int(confidence) < self.config.confidence_threshold
        except (ValueError, TypeError):
            return True

    def _handle_error(self, context: str, error: Exception | None):
        """Report error via callback if configured."""
        if self.config.on_error:
            self.config.on_error(context, error)

    def empty_score(self, item_id: str) -> dict:
        """Return a fallback score dict for a failed item."""
        return {self.config.id_field: item_id, "notes": "scoring failed"}
