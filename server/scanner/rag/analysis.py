import os
import logging
import traceback

from .heuristics import build_risk_summary, select_priority_chunks
from .prompts import create_enhanced_prompt
from .llm import get_ready_llm
from .extract import extract_relevant_info

logger = logging.getLogger(__name__)

# Only scan useful source files
SUPPORTED_EXTENSIONS = [
    "py", "js", "java", "c", "cpp", "go", "php", "rb", "ts", "jsx", "tsx",
    "html", "css", "cs", "kt", "kts", "scala", "h", "cc", "cxx", "hpp",
    "hh", "hxx", "htm", "sql", "swift", "rs", "sh", "m", "dart", "r",
    "pl", "pm", "xml", "yaml", "yml",
]

# Skip files that are almost never vulnerable (reduces noise + tokens)
SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock",
    "composer.lock", ".gitignore", ".gitattributes", "LICENSE", "CHANGELOG",
}

# Files larger than this (chars) use tighter context windows
LARGE_FILE_THRESHOLD = int(os.getenv("SCAN_LARGE_FILE_THRESHOLD", "8000"))


def scan_single_file(file_path: str, scan_id: str = None, triggered_by: str = None) -> list[dict]:
    """
    Scan a single file for vulnerabilities using the fine-tuned LLM.
    Returns a list of structured finding dicts (may be empty).
    """
    findings = []

    try:
        file_name = os.path.basename(file_path)

        # ---- Skip known non-code files ----
        if file_name in SKIP_FILENAMES:
            return []

        file_extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if file_extension not in SUPPORTED_EXTENSIONS:
            return []

        # ---- Read content ----
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError as e:
            logger.warning("Cannot read %s: %s", file_path, e)
            return []

        if not content.strip():
            return []

        logger.info("Scanning %s (%d chars)", file_name, len(content))

        # ---- Select risky chunks ----
        # Tighter context window for large files keeps each prompt compact.
        ctx = 12 if len(content) > LARGE_FILE_THRESHOLD else 15
        chunks = select_priority_chunks(content, file_extension, context_window=ctx)

        if not chunks:
            return []

        llm_client = get_ready_llm()
        seen_snippets: set[str] = set()  # dedup findings within the same file

        for chunk in chunks:
            try:
                risk_signals = build_risk_summary(chunk)

                # Skip chunks with zero risk signals — nothing interesting here
                if not risk_signals:
                    logger.debug("Skipping low-risk chunk in %s", file_name)
                    continue

                prompt = create_enhanced_prompt(
                    chunk=chunk,
                    file_name=file_name,
                    file_extension=file_extension,
                    risk_signals=risk_signals,
                )

                # Prompt trimming is handled inside llm_client.invoke()
                # via truncate_prompt() — no manual slicing needed here.
                response = llm_client.invoke({"query": prompt})

                if not response:
                    continue

                result_text = response.get("result", "").strip()

                if not result_text or "NO_VULNERABILITY_FOUND" in result_text:
                    continue

                # ---- Parse structured findings from LLM output ----
                parsed = extract_relevant_info(
                    llm_output=result_text,
                    file_name=file_name,
                    scan_id=scan_id,
                    triggered_by=triggered_by,
                    file_content=content,
                )

                for finding in parsed:
                    # Deduplicate by snippet fingerprint within the same file
                    snip_key = finding.get("code_snip", "")[:120]
                    if snip_key in seen_snippets:
                        continue
                    seen_snippets.add(snip_key)
                    findings.append(finding)

            except Exception as chunk_error:
                logger.error(
                    "Error processing chunk in %s: %s\n%s",
                    file_name, chunk_error, traceback.format_exc(),
                )
                continue

    except Exception as e:
        logger.error("Failed scanning %s: %s\n%s", file_path, e, traceback.format_exc())

    return findings