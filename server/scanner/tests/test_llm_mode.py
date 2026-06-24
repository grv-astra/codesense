import os
from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.llm import model_mode


class ModelModeTests(SimpleTestCase):
    def test_defaults_to_fim(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LLM_MODEL_MODE", None)
            self.assertEqual(model_mode(), "fim")

    def test_instruct_when_set(self):
        with mock.patch.dict(os.environ, {"LLM_MODEL_MODE": "instruct"}):
            self.assertEqual(model_mode(), "instruct")

    def test_instruct_is_case_insensitive(self):
        with mock.patch.dict(os.environ, {"LLM_MODEL_MODE": "Instruct"}):
            self.assertEqual(model_mode(), "instruct")

    def test_unknown_value_falls_back_to_fim(self):
        with mock.patch.dict(os.environ, {"LLM_MODEL_MODE": "fancy"}):
            self.assertEqual(model_mode(), "fim")
