"""Tests for device-tier → GGUF filename resolution (roadmap W5.1).

Pure config: the build/launcher picks a tier; this keeps the tier→filename
mapping and the MODEL_TIER env reading in one tested place. No model files
needed.
"""
import os
from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.model_tiers import gguf_filename_for_tier, model_tier


class GgufFilenameForTierTests(SimpleTestCase):
    def test_tiers_map_to_filenames(self):
        self.assertEqual(gguf_filename_for_tier("low"), "astra-1.5B.gguf")
        self.assertEqual(gguf_filename_for_tier("mid"), "astra-7B.gguf")
        self.assertEqual(gguf_filename_for_tier("high"), "astra-14B.gguf")

    def test_unknown_defaults_to_mid(self):
        self.assertEqual(gguf_filename_for_tier("bogus"), "astra-7B.gguf")

    def test_case_insensitive(self):
        self.assertEqual(gguf_filename_for_tier("HIGH"), "astra-14B.gguf")
        self.assertEqual(gguf_filename_for_tier("Mid"), "astra-7B.gguf")

    def test_none_and_empty_default_to_mid(self):
        self.assertEqual(gguf_filename_for_tier(None), "astra-7B.gguf")
        self.assertEqual(gguf_filename_for_tier(""), "astra-7B.gguf")

    def test_whitespace_is_tolerated(self):
        self.assertEqual(gguf_filename_for_tier("  low  "), "astra-1.5B.gguf")


class ModelTierTests(SimpleTestCase):
    def test_default_is_mid_when_env_unset(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(model_tier(), "mid")

    def test_reads_model_tier_env(self):
        with mock.patch.dict(os.environ, {"MODEL_TIER": "high"}, clear=True):
            self.assertEqual(model_tier(), "high")
        with mock.patch.dict(os.environ, {"MODEL_TIER": "low"}, clear=True):
            self.assertEqual(model_tier(), "low")

    def test_bogus_env_falls_back_to_mid(self):
        with mock.patch.dict(os.environ, {"MODEL_TIER": "enormous"}, clear=True):
            self.assertEqual(model_tier(), "mid")

    def test_env_is_normalized(self):
        with mock.patch.dict(os.environ, {"MODEL_TIER": "  HIGH "}, clear=True):
            self.assertEqual(model_tier(), "high")

    def test_resolved_tier_round_trips_to_filename(self):
        with mock.patch.dict(os.environ, {"MODEL_TIER": "low"}, clear=True):
            self.assertEqual(gguf_filename_for_tier(model_tier()), "astra-1.5B.gguf")
