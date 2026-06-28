"""Instruct-mode behavior for VLLMClient.invoke / _clean_output.

When LLM_MODEL_MODE=instruct the client must send a system prompt, forward an
optional response_format, drop the FIM stop-tokens, and pass output through
unmangled. With the flag off (default fim) the request and output-cleaning must
be byte-for-byte the legacy behavior.
"""
import os
from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.llm import VLLMClient, _STOP_TOKENS


def _ok_post():
    return mock.Mock(
        status_code=200,
        json=lambda: {"choices": [{"message": {"content": '{"ok": true}'}}]},
    )


class InstructRequestTests(SimpleTestCase):
    @mock.patch.dict(os.environ, {"LLM_MODEL_MODE": "instruct"})
    @mock.patch("scanner.rag.llm.requests.post")
    def test_instruct_sends_system_msg_json_format_and_no_fim_stops(self, mock_post):
        mock_post.return_value = _ok_post()
        c = VLLMClient()
        c.invoke({"query": "hi", "response_format": {"type": "json_object"}})
        body = mock_post.call_args.kwargs["json"]
        roles = [m["role"] for m in body["messages"]]
        self.assertIn("system", roles)
        self.assertEqual(body.get("response_format"), {"type": "json_object"})
        # no FIM stop-tokens forced on the server in instruct mode
        self.assertNotIn("<|fim_middle|>", body.get("stop", []))
        self.assertNotIn("stop", body)

    @mock.patch.dict(os.environ, {"LLM_MODEL_MODE": "instruct"})
    @mock.patch("scanner.rag.llm.requests.post")
    def test_instruct_without_response_format_omits_the_key(self, mock_post):
        mock_post.return_value = _ok_post()
        c = VLLMClient()
        c.invoke({"query": "hi"})
        body = mock_post.call_args.kwargs["json"]
        self.assertNotIn("response_format", body)
        self.assertIn("system", [m["role"] for m in body["messages"]])

    @mock.patch.dict(os.environ, {"LLM_MODEL_MODE": "instruct"})
    def test_instruct_clean_output_is_passthrough(self):
        c = VLLMClient()
        # FIM echo-hunting must NOT mangle clean JSON in instruct mode
        self.assertEqual(c._clean_output('{"verdict":"FP"}'), '{"verdict":"FP"}')
        weird = 'Analyze this\n{"verdict":"TP"}'
        self.assertEqual(c._clean_output(weird), weird)


class FimRequestUnchangedTests(SimpleTestCase):
    """Guard: with the flag off, the legacy FIM behavior is preserved exactly."""

    @mock.patch.dict(os.environ, {}, clear=False)
    @mock.patch("scanner.rag.llm.requests.post")
    def test_fim_sends_stop_tokens_no_system_no_response_format(self, mock_post):
        os.environ.pop("LLM_MODEL_MODE", None)
        mock_post.return_value = _ok_post()
        c = VLLMClient()
        # response_format must be ignored in fim mode (never forwarded)
        c.invoke({"query": "hi", "response_format": {"type": "json_object"}})
        body = mock_post.call_args.kwargs["json"]
        self.assertEqual(body.get("stop"), _STOP_TOKENS)
        self.assertEqual([m["role"] for m in body["messages"]], ["user"])
        self.assertNotIn("response_format", body)

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_fim_clean_output_still_hunts_echo(self):
        os.environ.pop("LLM_MODEL_MODE", None)
        c = VLLMClient()
        # the FIM cleaner keeps content from the first "Vulnerability:" marker
        echoed = "Analyze this code\nVulnerability: SQLi found here"
        self.assertEqual(c._clean_output(echoed), "Vulnerability: SQLi found here")
