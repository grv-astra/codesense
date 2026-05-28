import logging
import os
import time
import threading
from typing import Any

import requests
from .config import get_qa_chain, set_qa_chain

logger = logging.getLogger(__name__)
_CLIENT_LOCK = threading.Lock()

# This model is a fill-in-the-middle (FIM) model used via chat endpoint.
# It echoes the user prompt and repeats after <|fim_middle|>.
# We use NO system prompt (wastes tokens, confuses the model) and
# stop generation at the known repetition markers.
_STOP_TOKENS = [
    "<|fim_middle|>",
    "<|endoftext|>",
    "\nAnalyze this",   # model starts repeating the prompt
    "\n```\n\nAnalyze", # another repeat pattern observed
]

# Conservative chars-per-token for code (code tokenises denser than prose)
_CHARS_PER_TOKEN = 3.5


def _normalize_base_url(base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        base = "http://127.0.0.1:8001/v1"
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


class VLLMConnectionError(RuntimeError):
    pass


class VLLMClient:
    def __init__(self):
        self.base_url = _normalize_base_url(os.getenv("VLLM_BASE_URL"))
        self.model    = os.getenv("VLLM_MODEL", "astra-code-reviewer")
        self.api_key  = os.getenv("VLLM_API_KEY", "EMPTY")
        self.timeout  = int(os.getenv("VLLM_TIMEOUT_SECONDS", "120"))
        self.temperature = float(os.getenv("VLLM_TEMPERATURE", "0.05"))

        # Actual context window — fetched live from the server so env vars
        # can never be stale.
        self.max_model_len = self._fetch_actual_model_len(
            int(os.getenv("VLLM_MAX_MODEL_LEN", "4096"))
        )

        # Output token budget: cap at 1/3 of context so there is always
        # room for the input prompt.  200 is enough for the structured format.
        self.max_tokens = min(
            int(os.getenv("VLLM_MAX_TOKENS", "200")),
            max(64, self.max_model_len // 3),
        )

        # Tokens reserved for model-internal overhead
        self._overhead  = 64
        self.retry_attempts = 2

    # ------------------------------------------------------------------ #
    # STARTUP: detect real context length from the server
    # ------------------------------------------------------------------ #

    def _fetch_actual_model_len(self, fallback: int) -> int:
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5,
            )
            if resp.status_code == 200:
                for model in resp.json().get("data", []):
                    ctx = model.get("max_model_len") or model.get("context_length")
                    if ctx:
                        logger.info("Server max_model_len=%d", int(ctx))
                        return int(ctx)
        except Exception:
            pass
        logger.info("Using fallback max_model_len=%d", fallback)
        return fallback

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ #
    # TOKEN BUDGET
    # ------------------------------------------------------------------ #

    def _estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text) / _CHARS_PER_TOKEN))

    def _max_prompt_chars(self) -> int:
        """Max characters the prompt may be so total stays inside context."""
        budget = self.max_model_len - self.max_tokens - self._overhead
        return max(256, int(budget * _CHARS_PER_TOKEN))

    def truncate_prompt(self, prompt: str) -> tuple[str, bool]:
        """
        Trim prompt to fit context window before sending.
        Keeps the instruction header and trims the code block (largest part).
        """
        limit = self._max_prompt_chars()
        if len(prompt) <= limit:
            return prompt, False

        # Trim inside the code block, preserving the header
        marker = "```"
        last_fence = prompt.rfind(marker, 0, limit)
        if last_fence != -1:
            truncated = prompt[:last_fence] + "\n[truncated]\n```"
        else:
            truncated = prompt[:limit]

        logger.debug("Prompt trimmed %d→%d chars", len(prompt), len(truncated))
        return truncated, True

    def _safe_max_tokens(self, prompt: str) -> int:
        input_tokens = self._estimate_tokens(prompt)
        available    = self.max_model_len - input_tokens - self._overhead
        if available <= 0:
            return 32
        return min(self.max_tokens, available)

    # ------------------------------------------------------------------ #
    # OUTPUT CLEANING — handles FIM model's echo + repeat artefacts
    # ------------------------------------------------------------------ #

    def _clean_output(self, content: str) -> str:
        if not content:
            return ""

        content = content.strip()

        # ── 1. Cut at known FIM / repetition stop markers ──────────────
        for marker in _STOP_TOKENS:
            if marker in content:
                content = content.split(marker)[0].strip()

        # ── 2. The model echoes the user prompt before answering.
        #       Find the FIRST "Vulnerability:" and keep from there.
        vuln_idx = content.find("Vulnerability:")
        if vuln_idx != -1:
            content = content[vuln_idx:].strip()

        # ── 3. If there are multiple Vulnerability: blocks (extra repeat),
        #       keep only the first clean one.
        if content.count("Vulnerability:") > 1:
            parts = content.split("Vulnerability:")
            # Rebuild just the first block
            content = "Vulnerability:" + parts[1]

        # ── 4. Strip escaped newlines the model sometimes emits ─────────
        #       e.g. "requests.get(url)\\n" → "requests.get(url)\n"
        content = content.replace("\\n", "\n").replace("\\\\n", "\n")

        # ── 5. Strip trailing code fence noise ──────────────────────────
        if content.endswith("```"):
            pass   # fine, keep it
        # Remove stray backslashes before closing fences
        content = content.replace("\\\n```", "\n```")

        return content.strip()

    # ------------------------------------------------------------------ #
    # HEALTHCHECK
    # ------------------------------------------------------------------ #

    def healthcheck(self) -> dict:
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=10,
            )
            response.raise_for_status()
            data   = response.json()
            models = [m.get("id", "") for m in data.get("data", [])]
            return {
                "base_url":          self.base_url,
                "configured_model":  self.model,
                "available_models":  models,
            }
        except Exception as e:
            raise VLLMConnectionError(f"vLLM not reachable: {e}")

    # ------------------------------------------------------------------ #
    # MAIN INVOKE
    # ------------------------------------------------------------------ #

    def invoke(self, payload: dict[str, Any]) -> dict[str, str]:
        prompt = payload.get("query", "")

        # Trim client-side first — avoids 400 entirely
        prompt, _ = self.truncate_prompt(prompt)
        safe_max   = self._safe_max_tokens(prompt)

        for attempt in range(self.retry_attempts):
            try:
                body = {
                    "model":       self.model,
                    "temperature": self.temperature,
                    "max_tokens":  safe_max,
                    "stop":        _STOP_TOKENS,   # ← tell the server to stop at repeat markers
                    # NO system prompt — this FIM model ignores / mishandles it
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                }

                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=body,
                    timeout=self.timeout,
                )

                if response.status_code == 400:
                    try:
                        err = response.json()
                    except Exception:
                        err = response.text[:300]
                    logger.warning("vLLM 400 (attempt %d/%d): %s",
                                   attempt + 1, self.retry_attempts, err)
                    if attempt < self.retry_attempts - 1:
                        time.sleep(0.5)
                        continue
                    return {"result": ""}

                response.raise_for_status()

                content = (
                    response.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

                return {"result": self._clean_output(content)}

            except VLLMConnectionError:
                raise
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    raise VLLMConnectionError(str(e))
                time.sleep(1)

        return {"result": ""}


# ------------------------------------------------------------------ #
# SINGLETON
# ------------------------------------------------------------------ #

def get_llm() -> VLLMClient:
    return VLLMClient()


def get_ready_llm(force_healthcheck: bool = False) -> VLLMClient:
    client = get_qa_chain()
    if client and not force_healthcheck:
        return client

    with _CLIENT_LOCK:
        client = get_qa_chain()
        if client and not force_healthcheck:
            return client

        client = get_llm()
        client.healthcheck()
        set_qa_chain(client)
        logger.info("vLLM client initialized successfully.")
        return client