from datetime import datetime, timezone
from bson import ObjectId
import logging
import re
import uuid
import difflib
 
logger = logging.getLogger(__name__)
 
# -----------------------------
# Utilities
# -----------------------------
 
def _normalize_newlines(s: str) -> str:
    """Normalize newlines to '\n' only; keep everything else intact."""
    return s.replace("\r\n", "\n").replace("\r", "\n")
 
def _normalize_quotes(s: str) -> str:
    """Normalize curly quotes to straight quotes to reduce false negatives."""
    return (
        s.replace("“", '"').replace("”", '"')
         .replace("‘", "'").replace("’", "'")
    )
 
def _build_whitespace_flexible_pattern(snippet: str) -> re.Pattern:
    """
    Build a regex pattern from the snippet that matches even if the file has
    different indentation or spacing. We:
      - trim ends
      - escape all literal chars
      - replace any run of whitespace in the snippet with '\\s+'
    """
    trimmed = snippet.strip()
    # Escape literal characters
    escaped = re.escape(trimmed)
    # Collapse runs of whitespace in the *snippet* to \s+ so any whitespace in file matches
    pattern_str = re.sub(r'\s+', r'\\s+', escaped)
    return re.compile(pattern_str, flags=re.DOTALL)
 
def _count_line_number(upto_index: int, text_with_unified_newlines: str) -> int:
    """1-based line number for the character index in text."""
    return text_with_unified_newlines.count("\n", 0, upto_index) + 1
 
def _best_line_window_match(file_lines, snippet_lines, pad=6):
    """
    Fallback: find the window of lines in the file most similar to the snippet lines.
    Returns (start_line, end_line, score) with 1-based line numbers or (None, None, 0).
    """
    n = len(snippet_lines)
    if n == 0 or len(file_lines) == 0:
        return None, None, 0.0
 
    # Use a sliding window roughly matching snippet length (±pad)
    best = (None, None, 0.0)
    min_len = max(1, n - pad)
    max_len = min(len(file_lines), n + pad)
 
    # Pre-join snippet for faster comparison
    snippet_join = "\n".join(snippet_lines)
 
    for win_len in range(min_len, max_len + 1):
        # Evaluate in chunks to avoid O(N^2) for very long files
        for i in range(0, max(1, len(file_lines) - win_len + 1)):
            window = file_lines[i:i + win_len]
            window_join = "\n".join(window)
            score = difflib.SequenceMatcher(None, snippet_join, window_join).ratio()
            if score > best[2]:
                # Return as 1-based line numbers inclusive
                best = (i + 1, i + win_len, score)
    return best
 
# -----------------------------
# Public helpers used by caller
# -----------------------------
 
def clean_and_validate_field(field_value, max_length=None):
    """Clean and validate field values for display/storage (NOT for matching)."""
    if not field_value:
        return ""
    cleaned = ' '.join(field_value.strip().split())  # collapse spaces/newlines to single spaces
    if max_length and len(cleaned) > max_length:
        cleaned = cleaned[:max_length-3] + "..."
    return cleaned
 
def extract_vulnerable_function(file_content: str, snippet: str):
    """
    Return (extracted_text, [start_line, end_line]) where lines are 1-based and
    correspond to the exact region that matches the provided snippet.
   
    Strategy:
      1) Try exact substring on newline-normalized, quote-normalized content.
      2) Try whitespace-flexible regex over the original content (with unified newlines).
      3) Fallback: line-window similarity to approximate best match.
      4) If all fail: return [1,1].
    """
    if not snippet or not snippet.strip():
        return "No code snippet available", [1, 1]
 
    try:
        # Keep original for final extraction, but normalize newlines for indexing/line counts
        content_unified = _normalize_newlines(file_content)
        content_for_search = _normalize_quotes(content_unified)
 
        # Prepare a search-friendly version of the snippet
        snippet_unified = _normalize_newlines(snippet)
        snippet_for_search = _normalize_quotes(snippet_unified)
 
        # ---- 1) Direct exact match
        idx = content_for_search.find(snippet_for_search)
        if idx != -1:
            start_line = _count_line_number(idx, content_unified)
            end_line = _count_line_number(idx + len(snippet_for_search), content_unified)
            # Extract exactly those lines (inclusive)
            lines = content_unified.split("\n")
            extracted = "\n".join(lines[start_line-1:end_line])
            return extracted, [start_line, end_line]
 
        # ---- 2) Whitespace-flexible regex match
        pattern = _build_whitespace_flexible_pattern(snippet_for_search)
        m = pattern.search(content_for_search)
        if m:
            start_idx, end_idx = m.span()
            start_line = _count_line_number(start_idx, content_unified)
            end_line = _count_line_number(end_idx, content_unified)
            lines = content_unified.split("\n")
            extracted = "\n".join(lines[start_line-1:end_line])
            return extracted, [start_line, end_line]
 
        # ---- 3) Fallback: line-window similarity
        # Use non-empty, stripped lines from snippet for better robustness
        snippet_lines = [ln.rstrip() for ln in snippet_unified.split("\n") if ln.strip()]
        file_lines = content_unified.split("\n")
 
        s_line, e_line, score = _best_line_window_match(file_lines, snippet_lines, pad=6)
        # Require a reasonable similarity to avoid bogus [1,1]
        if s_line is not None and score >= 0.6:
            extracted = "\n".join(file_lines[s_line-1:e_line])
            return extracted, [s_line, e_line]
 
        # ---- 4) Give up
        return snippet, [1, 1]
 
    except Exception as e:
        logger.warning(f"Error extracting vulnerable function: {e}")
        return snippet, [1, 1]
 
 
def extract_relevant_info(llm_output, file_name, scan_id, triggered_by, file_content):
    """
    Extract relevant security vulnerabilities from the LLM output and attach accurate
    [start_line, end_line] for where the snippet occurs in the file.
    """
    if not llm_output or not isinstance(llm_output, str):
        return []
 
    vulnerabilities = []
 
    patterns = [
        re.compile(
            r"Vulnerability:\s*(.*?)\s*\n"
            r"CWE:\s*(.*?)\s*\n"
            r"Severity:\s*(.*?)\s*\n"
            r"Impact:\s*(.*?)\s*\n"
            r"Mitigation:\s*(.*?)\s*\n"
            r"Affected:\s*(.*?)\s*\n"
            r"Code Snippet:\s*(.*?)\s*(?=\n\n|\nVulnerability:|\Z)",
            re.DOTALL | re.IGNORECASE
        ),
        re.compile(
            r"(?:Issue|Problem|Security Issue):\s*(.*?)\n"
            r"(?:CWE|Type|Category):\s*(.*?)\n"
            r"(?:Risk|Severity|Level):\s*(.*?)\n"
            r"(?:Description|Impact|Risk Description):\s*(.*?)\n"
            r"(?:Fix|Solution|Mitigation|Recommendation):\s*(.*?)\n"
            r"(?:Location|File|Line|Function):\s*(.*?)\n"
            r"(?:Code|Snippet|Example):\s*(.*?)\s*(?=\n\n|\nIssue:|\Z)",
            re.DOTALL | re.IGNORECASE
        )
    ]
 
    for pattern in patterns:
        matches = pattern.findall(llm_output)
 
        for match in matches:
            if len(match) < 7:
                continue
 
            try:
                title = clean_and_validate_field(match[0], 200)
                cwe = clean_and_validate_field(match[1], 100)
                severity = clean_and_validate_field(match[2], 20).upper()
                impact = clean_and_validate_field(match[3], 1000)
                mitigation = clean_and_validate_field(match[4], 1000)
                affected = clean_and_validate_field(match[5], 200)
 
                # IMPORTANT: use raw snippet for matching to preserve formatting
                code_snippet_raw = match[6]
                # But keep a cleaned/truncated version for display/storage
                code_snippet_clean = clean_and_validate_field(match[6], 1000)
 
                if not title or not impact:
                    continue
 
                severity_mapping = {
                    'CRITICAL': ('CRITICAL', '9.8', 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'),
                    'HIGH':     ('HIGH', '8.8', 'CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H'),
                    'MEDIUM':   ('MEDIUM', '6.5', 'CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:L'),
                    'LOW':      ('LOW', '3.1', 'CVSS:3.1/AV:L/AC:H/PR:L/UI:R/S:U/C:L/I:N/A:N')
                }
 
                severity_normalized, cvss_score, cvss_vector = severity_mapping.get(
                    severity,
                    ('MEDIUM', '5.0', 'CVSS:3.1/AV:L/AC:H/PR:L/UI:N/S:U/C:L/I:L/A:N')
                )
 
                # Find exact snippet bounds (returns exact region + [start,end])
                matched_region, line_numbers = extract_vulnerable_function(
                    file_content, code_snippet_raw
                )
                start_line, end_line = line_numbers
 
                # Normalize/standardize CWE
                if cwe and not cwe.upper().startswith('CWE-'):
                    if cwe.isdigit():
                        cwe = f"CWE-{cwe}"
                    elif not any(keyword in cwe.lower() for keyword in ['cwe', 'common weakness']):
                        cwe = f"CWE-{cwe}"
 
                cwe_number_match = re.search(r'CWE-(\d+)', cwe)
                cwe_number = cwe_number_match.group(1) if cwe_number_match else "NA"
                reference_link = (
                    f"https://cwe.mitre.org/data/definitions/{cwe_number}.html"
                    if cwe_number != "NA" else "NA"
                )
 
                pocdesc = (
                    f"This proof of concept demonstrates how {title.lower()} can occur. {impact}"
                    if title and impact else
                    "No PoC description provided."
                )
 
                vulnerability = {
                    "scan_id": ObjectId(scan_id),
                    "cwe": cwe or "CWE-Unknown",
                    "cvss_vector": cvss_vector,
                    "cvss_score": cvss_score,
                    "code": 'f-' + str(uuid.uuid4()).replace('-', '')[:8],
                    "title": title,
                    "description": pocdesc,
                    "severity": severity_normalized.lower(),
                    # Keep existing file_path format if your downstream expects it:
                    "file_path": f"{file_name} [{start_line},{end_line}]",
                    # Store exact matched region (not expanded context)
                    "code_snip": matched_region[:2000],
                    "security_risk": impact,
                    "mitigation": mitigation,
                    "status": "open",
                    "deleted": False,
                    "approved": False,
                    "reference": reference_link,
                    "created_at": datetime.now(timezone.utc),
                    "created_by": ObjectId(triggered_by),
                    # Optional: add explicit numeric lines array for your DB if you want true "array form"
                    "lines": [start_line, end_line],
                    "affected": affected
                }
 
                vulnerabilities.append(vulnerability)
 
            except Exception as e:
                logging.warning(f"Error processing vulnerability match: {e}")
                continue
 
    return vulnerabilities