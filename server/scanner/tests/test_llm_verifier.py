from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.llm_verifier import build_verifier_prompt, verify
from scanner.rag.lsast_types import DataflowContext, VerifierVerdict


def _ctx() -> DataflowContext:
    return DataflowContext(
        source_line=12, source_code="request.GET['q']",
        sink_line=18, sink_code="cursor.execute(query)",
        steps=[(14, "query = '...' + q + '...'")],
        sanitizers_observed=[],
    )


class BuildVerifierPromptTests(SimpleTestCase):
    def test_includes_cwe_dataflow_and_json_instruction(self):
        prompt = build_verifier_prompt(
            cwe="CWE-89", language="python",
            dataflow=_ctx(),
            code_excerpt="q = request.GET['q']\ncursor.execute(query)",
        )
        self.assertIn("CWE-89", prompt)
        self.assertIn("Source", prompt)
        self.assertIn("Sink", prompt)
        self.assertIn("JSON", prompt)
        self.assertIn('"verdict"', prompt)
        self.assertNotIn("Risk indicators detected", prompt)         # must NOT pre-hint
        self.assertNotIn("vulnerable", prompt.lower().split("question:")[0])


class VerifyTests(SimpleTestCase):
    def _mock_llm(self, response_text: str):
        client = mock.Mock()
        client.invoke.return_value = {"result": response_text}
        return client

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_returns_TP_verdict_when_model_says_so(self, mock_get):
        mock_get.return_value = self._mock_llm(
            '{"verdict":"TP","reason":"unsanitized input flows to execute","confidence":0.95}')
        v = verify(cwe="CWE-89", language="python", dataflow=_ctx(), code_excerpt="…")
        self.assertEqual(v.verdict, "TP")
        self.assertAlmostEqual(v.confidence, 0.95)

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_returns_FP_verdict(self, mock_get):
        mock_get.return_value = self._mock_llm(
            '{"verdict":"FP","reason":"parameterized query","confidence":0.9}')
        v = verify(cwe="CWE-89", language="python", dataflow=_ctx(), code_excerpt="…")
        self.assertEqual(v.verdict, "FP")

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_strips_code_fences_around_json(self, mock_get):
        mock_get.return_value = self._mock_llm(
            '```json\n{"verdict":"FP","reason":"safe","confidence":0.8}\n```')
        v = verify(cwe="CWE-89", language="python", dataflow=_ctx(), code_excerpt="…")
        self.assertEqual(v.verdict, "FP")

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_extracts_json_when_model_adds_prose(self, mock_get):
        mock_get.return_value = self._mock_llm(
            'Sure! Here is my analysis: {"verdict":"TP","reason":"concat","confidence":0.7} Hope that helps.')
        v = verify(cwe="CWE-89", language="python", dataflow=_ctx(), code_excerpt="…")
        self.assertEqual(v.verdict, "TP")

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_fails_open_on_unparseable_response(self, mock_get):
        mock_get.return_value = self._mock_llm("I think this might be unsafe.")
        v = verify(cwe="CWE-89", language="python", dataflow=_ctx(), code_excerpt="…")
        self.assertEqual(v.verdict, "TP")            # fail-open: preserve finding
        self.assertLess(v.confidence, 0.5)
        self.assertIn("unparseable", v.reason.lower())

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_fails_open_on_llm_exception(self, mock_get):
        client = mock.Mock()
        client.invoke.side_effect = RuntimeError("model busy")
        mock_get.return_value = client
        v = verify(cwe="CWE-89", language="python", dataflow=_ctx(), code_excerpt="…")
        self.assertEqual(v.verdict, "TP")
        self.assertLess(v.confidence, 0.5)
