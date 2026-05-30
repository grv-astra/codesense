import unittest
from eval.matching import Case
from eval.runner import (run_detector_tier, run_detector_tier_by_language,
                         build_balanced_sample, run_verifier_tier)


def _case(cid, real, cwe="CWE-89", path=None):
    return Case(case_id=cid, source_path=path or f"/src/{cid}.java", is_real=real, cwe=cwe)


def _fake_scan(path):
    mapping = {
        "/src/real_hit.java": [{"file_path": "real_hit.java [1,2]", "cwe": "CWE-89"}],
        "/src/fake_flagged.java": [{"file_path": "fake_flagged.java [1,2]", "cwe": "CWE-89"}],
    }
    return mapping.get(path, [])


class DetectorTierTests(unittest.TestCase):
    def test_counts_tp_fp_fn_tn(self):
        cases = [_case("real_hit", True), _case("real_miss", True),
                 _case("fake_clean", False), _case("fake_flagged", False)]
        counts = run_detector_tier(cases, scan_fn=_fake_scan)
        self.assertEqual((counts.tp, counts.fn, counts.tn, counts.fp), (1, 1, 1, 1))

    def test_per_language_groups_by_lang_fn(self):
        cases = [_case("real_hit", True, path="/src/real_hit.java"),
                 _case("py1", True, path="/src/py1.py")]
        # py1 produces no finding (fake_scan returns []) → fn under python
        def lang_fn(p):
            return "python" if p.endswith(".py") else "java"
        by_lang = run_detector_tier_by_language(cases, scan_fn=_fake_scan, lang_fn=lang_fn)
        self.assertEqual(by_lang["java"].tp, 1)
        self.assertEqual(by_lang["python"].fn, 1)


class SampleTests(unittest.TestCase):
    def test_balanced_sample_stratifies(self):
        cases = [_case(f"r{i}", True) for i in range(10)] + [_case(f"f{i}", False) for i in range(10)]
        sample = build_balanced_sample(cases, per_class=3)
        self.assertEqual(len([c for c in sample if c.is_real]), 3)
        self.assertEqual(len([c for c in sample if not c.is_real]), 3)


class _V:
    def __init__(self, verdict): self.verdict = verdict


class VerifierTierTests(unittest.TestCase):
    def test_counts_and_caches(self):
        calls = []
        def verify_fn(**kw):
            calls.append(kw["cwe"])
            return _V("TP") if "89" in kw["cwe"] else _V("FP")
        samples = [
            {"cwe": "CWE-89", "language": "python", "dataflow": "d", "code": "a", "is_real": True},   # kept → tp
            {"cwe": "CWE-79", "language": "python", "dataflow": "d", "code": "b", "is_real": False},  # dropped(FP) → tn
            {"cwe": "CWE-89", "language": "python", "dataflow": "d", "code": "a", "is_real": True},   # same (cwe,code) → cached, no 2nd call
        ]
        counts = run_verifier_tier(samples, verify_fn=verify_fn)
        self.assertEqual(counts.tp, 2)   # both is_real CWE-89 kept
        self.assertEqual(counts.tn, 1)
        self.assertEqual(len(calls), 2)  # third reused cache


if __name__ == "__main__":
    unittest.main()
