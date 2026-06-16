"""Gated live round-trip test against a running llama-server / vLLM endpoint.

Skipped unless LLM_LIVE_TEST=1 with a reachable server (set VLLM_BASE_URL, and
LLM_MODEL_MODE=instruct to exercise the instruct path). Never runs in the normal
offline suite, so it cannot flake CI.

Run (with an instruct server up):
  cd server && LLM_LIVE_TEST=1 LLM_MODEL_MODE=instruct \
    VLLM_BASE_URL=http://127.0.0.1:8001/v1 \
    .venv/Scripts/python.exe manage.py test scanner.tests.test_llm_integration -v 2
"""
import os
import unittest

from django.test import SimpleTestCase

from scanner.rag.llm import get_ready_llm, model_mode

_LIVE = os.getenv("LLM_LIVE_TEST") == "1"


@unittest.skipUnless(_LIVE, "set LLM_LIVE_TEST=1 with a running llama-server")
class LlmRoundTripTests(SimpleTestCase):
    def test_chat_roundtrip_returns_text(self):
        client = get_ready_llm(force_healthcheck=True)
        out = client.invoke({"query": "Reply with the single word: ok"}) or {}
        self.assertTrue((out.get("result") or "").strip())

    def test_instruct_response_format_path_roundtrips(self):
        """Exercise the instruct + response_format transport against a live
        server: it must round-trip non-empty text. This is a TRANSPORT check,
        not a model-quality assertion — whether the reply is clean JSON depends
        on the served model actually being instruction-tuned (measured by the
        eval harness / verifier A/B, not here). Skipped unless instruct mode."""
        if model_mode() != "instruct":
            self.skipTest("not in instruct mode (set LLM_MODEL_MODE=instruct)")
        client = get_ready_llm(force_healthcheck=True)
        out = client.invoke({
            "query": 'Return this exact JSON: {"status": "ok"}',
            "response_format": {"type": "json_object"},
        }) or {}
        self.assertTrue((out.get("result") or "").strip(),
                        "empty response from live server")
