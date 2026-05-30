from django.test import SimpleTestCase
from scanner.rag.languages import LANGUAGES, language_for_path, UNKNOWN


class LanguageRegistryTests(SimpleTestCase):
    def test_has_at_least_40_languages(self):
        self.assertGreaterEqual(len(LANGUAGES), 40)

    def test_extensions_are_unique_across_registry(self):
        seen = {}
        for lang in LANGUAGES:
            for ext in lang.extensions:
                self.assertNotIn(ext, seen, f"{ext} in both {seen.get(ext)} and {lang.name}")
                seen[ext] = lang.name

    def test_coverage_tiers_valid(self):
        for lang in LANGUAGES:
            self.assertIn(lang.coverage, ("strong", "partial", "none"))

    def test_strong_and_partial_langs_have_semgrep_id(self):
        for lang in LANGUAGES:
            if lang.coverage in ("strong", "partial"):
                self.assertTrue(lang.semgrep_lang, f"{lang.name} needs a semgrep id")

    def test_language_for_path_python(self):
        lang = language_for_path("app/views.py")
        self.assertEqual(lang.name, "python")
        self.assertEqual(lang.coverage, "strong")

    def test_language_for_path_is_case_insensitive(self):
        self.assertEqual(language_for_path("Main.JAVA").name, "java")

    def test_language_for_path_unknown_extension(self):
        lang = language_for_path("data.xyzzy")
        self.assertIs(lang, UNKNOWN)
        self.assertEqual(lang.coverage, "none")

    def test_routing_only_language_present(self):
        cobol = language_for_path("payroll.cbl")
        self.assertEqual(cobol.name, "cobol")
        self.assertEqual(cobol.coverage, "none")
        self.assertIsNone(cobol.semgrep_lang)
