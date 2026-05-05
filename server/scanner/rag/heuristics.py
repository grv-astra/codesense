import re
import os

# ------------------------------------------------------------------ #
# CONFIGURABLE LIMITS (can be tuned via .env)
# ------------------------------------------------------------------ #
MAX_CHUNKS_PER_FILE = int(os.getenv("SCAN_MAX_CHUNKS_PER_FILE", "4"))
CONTEXT_LINES = int(os.getenv("SCAN_CONTEXT_LINES", "15"))   # lines around a hit
CHUNK_SIZE = int(os.getenv("SCAN_CHUNK_SIZE", "50"))          # fallback chunk lines

# ------------------------------------------------------------------ #
# SECURITY PATTERNS — weighted by likely severity
# ------------------------------------------------------------------ #

# Each entry: (label, [regex_list], weight)
# Weight is used to rank chunks — higher-weight regions get priority
RISK_PATTERNS: list[tuple[str, list[str], int]] = [
    ("Command Injection",   [r"os\.system\b", r"subprocess\.(call|run|Popen|check_output)\b",
                              r"exec\(", r"eval\(", r"shell=True"], 10),

    ("SQL Injection",       [r"\.execute\s*\(.*%[s|d]", r"\.execute\s*\(.*\+",
                              r"\.execute\s*\(.*format\b", r"\.execute\s*\(.*f[\"']",
                              r"cursor\.execute\b", r"mysqli_query\b",
                              r"raw\(", r"\.raw\s*\("], 10),

    ("Deserialization",     [r"pickle\.loads\b", r"pickle\.load\b",
                              r"yaml\.load\s*\((?!.*Loader\s*=\s*yaml\.SafeLoader)",
                              r"marshal\.loads\b", r"jsonpickle\.decode\b"], 9),

    ("SSRF / Ext Request",  [r"requests\.(get|post|put|delete|head|patch)\s*\(",
                              r"urllib\.request\.(urlopen|urlretrieve)\b",
                              r"http\.get\b", r"axios\.(get|post|put|delete)\b",
                              r"fetch\s*\("], 8),

    ("Path Traversal",      [r"open\s*\([^)]*\.\.", r"os\.path\.join\b",
                              r"send_file\b", r"send_from_directory\b",
                              r"\.\./", r"\.\.\\\\"], 8),

    ("User Input",          [r"request\.(args|form|data|json|files|values|params)\b",
                              r"\$_GET\b", r"\$_POST\b", r"\$_REQUEST\b",
                              r"req\.(body|query|params)\b",
                              r"getParameter\b", r"input\("], 7),

    ("Auth / Crypto",       [r"md5\s*\(", r"sha1\s*\(", r"hashlib\.md5\b",
                              r"hashlib\.sha1\b", r"SECRET\b", r"PASSWORD\b",
                              r"jwt\.decode\b", r"verify\s*=\s*False"], 7),

    ("XSS",                 [r"document\.write\s*\(", r"innerHTML\s*=",
                              r"\.html\s*\(", r"dangerouslySetInnerHTML\b",
                              r"render_template_string\b"], 7),

    ("File Operation",      [r"open\s*\(", r"\.write\s*\(", r"\.read\s*\(",
                              r"shutil\.(copy|move|rmtree)\b",
                              r"os\.(remove|unlink|rename)\b"], 5),

    ("Template Injection",  [r"render_template_string\b",
                              r"Jinja2\.from_string\b",
                              r"Template\s*\(.*\+",
                              r"Environment\s*\(.*autoescape\s*=\s*False"], 9),

    ("Hard-coded Secret",   [r"(api_key|apikey|secret|password|token|passwd)\s*=\s*[\"'][^\"']{6,}[\"']",
                              r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"], 8),
]

# Patterns that are almost never real vulnerabilities — skip those chunks
FALSE_POSITIVE_GUARDS: list[str] = [
    r"#.*example",
    r"#.*sample",
    r"#.*test",
    r"#.*mock",
    r"\"\"\".*example.*\"\"\"",
]


# ------------------------------------------------------------------ #
# RISK SUMMARY (used in prompt as hint)
# ------------------------------------------------------------------ #

def build_risk_summary(chunk: str) -> list[str]:
    """
    Return a deduplicated list of risk signal labels found in the chunk.
    Used as hints inside the LLM prompt to reduce hallucination.
    """
    signals = []
    for label, patterns, _weight in RISK_PATTERNS:
        for pat in patterns:
            if re.search(pat, chunk, flags=re.IGNORECASE):
                signals.append(label)
                break
    return signals


# ------------------------------------------------------------------ #
# CHUNK SCORING
# ------------------------------------------------------------------ #

def _score_chunk(chunk: str) -> int:
    """
    Return a numeric risk score for a chunk.
    Higher = more likely to contain a real vulnerability.
    """
    score = 0
    for _label, patterns, weight in RISK_PATTERNS:
        for pat in patterns:
            if re.search(pat, chunk, flags=re.IGNORECASE):
                score += weight
                break  # only count each category once per chunk
    return score


def _is_likely_false_positive_region(line: str) -> bool:
    """Cheap pre-filter: skip lines that are clearly test/example/comment code."""
    for pat in FALSE_POSITIVE_GUARDS:
        if re.search(pat, line, flags=re.IGNORECASE):
            return True
    return False


# ------------------------------------------------------------------ #
# MAIN CHUNK SELECTOR
# ------------------------------------------------------------------ #

def select_priority_chunks(
    file_content: str,
    file_extension: str,
    max_chunks: int = MAX_CHUNKS_PER_FILE,
    context_window: int = CONTEXT_LINES,
    chunk_size: int = CHUNK_SIZE,
) -> list[str]:
    """
    Select the most security-relevant chunks from a file.

    Strategy:
    1. Walk every line looking for risky patterns.
    2. Build context windows (±context_window lines) around each hit.
    3. Merge overlapping ranges to avoid duplicate content.
    4. Score each merged region and keep the top `max_chunks`.
    5. Fallback to even chunking if nothing matched.
    """
    lines = file_content.splitlines()
    if not lines:
        return []

    # Build a flat list of all pattern regexes for hit detection
    all_patterns: list[str] = []
    for _label, patterns, _w in RISK_PATTERNS:
        all_patterns.extend(patterns)

    # ---- 1. Find all hit lines ----
    hit_ranges: list[tuple[int, int]] = []

    for idx, line in enumerate(lines):
        if _is_likely_false_positive_region(line):
            continue
        for pat in all_patterns:
            if re.search(pat, line, flags=re.IGNORECASE):
                start = max(0, idx - context_window)
                end = min(len(lines), idx + context_window + 1)
                hit_ranges.append((start, end))
                break  # one match per line is enough

    # ---- 2. Fallback to even chunking ----
    if not hit_ranges:
        fallback = []
        for i in range(0, len(lines), chunk_size):
            fallback.append((i, min(len(lines), i + chunk_size)))
            if len(fallback) >= max_chunks:
                break
        return ["\n".join(lines[s:e]).strip() for s, e in fallback if lines[s:e]]

    # ---- 3. Merge overlapping / adjacent ranges ----
    hit_ranges.sort()
    merged: list[tuple[int, int]] = []
    cur_start, cur_end = hit_ranges[0]
    for s, e in hit_ranges[1:]:
        if s <= cur_end + 2:          # merge if touching or overlapping
            cur_end = max(cur_end, e)
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = s, e
    merged.append((cur_start, cur_end))

    # ---- 4. Score and rank ----
    scored: list[tuple[int, tuple[int, int]]] = []
    for s, e in merged:
        chunk_text = "\n".join(lines[s:e])
        scored.append((_score_chunk(chunk_text), (s, e)))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [rng for _score, rng in scored[:max_chunks]]
    # Re-sort by file order for natural reading
    top.sort()

    # ---- 5. Build final chunk strings ----
    chunks = []
    for s, e in top:
        chunk = "\n".join(lines[s:e]).strip()
        if chunk:
            chunks.append(chunk)

    return chunks