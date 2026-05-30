# LSAST eval harness (dev-host only — never bundled)

Measures the LSAST scanner vs the §9 thresholds (F1≥0.70, FP≤25%, recall≥0.60),
with a per-language detector-coverage table (ties the top-40 registry to real numbers).

## Tests
    cd <repo> && python3 -m unittest discover -s scripts/eval/tests -t scripts -v

## Run (curated, deterministic, CI)
    cd scripts/eval && PYTHONPATH=../../server python3 run_eval.py --dataset curated --tier detector --gate

## Full run (OWASP detector + verifier — needs network once + llama-server)
1. `git clone https://github.com/OWASP-Benchmark/BenchmarkJava` somewhere.
2. Export `OWASP_CSV=<repo>/expectedresults-1.2.csv` and
   `OWASP_SRC=<repo>/src/main/java/org/owasp/benchmark/testcode`.
3. Start the app (or llama-server) so `VLLM_BASE_URL` is reachable, for the sampled verifier pass.
4. `cd scripts/eval && PYTHONPATH=../../server python3 run_eval.py --dataset all --tier detector`

Results land in `scripts/eval/results/<UTC>.md`. `.cache/`, `results/`, and downloaded data are gitignored.
