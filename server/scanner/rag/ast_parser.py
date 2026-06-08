import os
import ast
from typing import Dict, List, Tuple, Set

SUPPORTED_LANGS = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "cpp": "cpp",
    "c": "c",
    "go": "go",
    "php": "php",
    "ruby": "ruby",
    "csharp": "c_sharp",
    "kotlin": "kotlin",
    "swift": "swift",
    "rust": "rust",
    "scala": "scala"
}

EXTENSION_MAP = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "java": "java",
    "cpp": "cpp",
    "cc": "cpp",
    "c": "c",
    "h": "c",
    "go": "go",
    "php": "php",
    "rb": "ruby",
    "cs": "csharp",
    "kt": "kotlin",
    "swift": "swift",
    "rs": "rust",
    "scala": "scala"
}

def detect_language(file_path: str) -> str:
    """Detect language using file extension only."""
    ext = os.path.splitext(file_path)[1][1:].lower()
    return EXTENSION_MAP.get(ext, "unknown")


def count_non_empty_lines(content: str) -> int:
    """Return total non-empty LOC."""
    return sum(1 for line in content.splitlines() if line.strip())


def count_python_functions(content: str) -> int:
    """Count Python functions using AST."""
    try:
        tree = ast.parse(content)
    except Exception:
        return 0

    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in ast.walk(tree)
    )


def count_other_language_functions(content: str, language: str) -> int:
    """
    Lightweight function counting using regex-based heuristics.
    Not perfect but fast and language-agnostic.
    """

    import re

    patterns = {
        "javascript": r"function\s+\w+|\w+\s*=\s*\(.*\)\s*=>",
        "typescript": r"function\s+\w+|\w+\s*=\s*\(.*\)\s*=>",
        "java": r"(public|private|protected)?\s+\w+\s+\w+\(.*\)",
        "cpp": r"\w+\s+\w+::\w+\(.*\)|\w+\s+\w+\(.*\)",
        "c": r"\w+\s+\w+\(.*\)",
        "go": r"func\s+\w+\(.*\)",
        "php": r"function\s+\w+\(.*\)",
        "ruby": r"def\s+\w+",
        "csharp": r"(public|private|protected)?\s+\w+\s+\w+\(.*\)",
        "kotlin": r"fun\s+\w+\(.*\)",
        "swift": r"func\s+\w+\(.*\)",
        "rust": r"fn\s+\w+\(.*\)",
        "scala": r"def\s+\w+\(.*\)",
    }

    pattern = patterns.get(language)
    if not pattern:
        return 0

    return len(re.findall(pattern, content))


def analyze_file_for_ast_metrics(file_path: str, file_content: str) -> Tuple[int, int, str]:
    """
    Returns:
    - loc (non-empty lines)
    - functions_count
    - language
    """

    language = detect_language(file_path)
    loc = count_non_empty_lines(file_content)

    if language == "python":
        functions = count_python_functions(file_content)
    else:
        functions = count_other_language_functions(file_content, language)

    return loc, functions, language


def analyze_folder(folder_path: str) -> Dict:
    """
    Analyze entire folder and return aggregated metrics:
    {
        "total_loc": ...,
        "total_functions": ...,
        "languages": [...]
    }
    """
    from .files import get_source_files, read_file

    total_loc = 0
    total_functions = 0
    total_files = 0
    languages: Set[str] = set()

    for file_path in get_source_files(folder_path):
        total_files += 1
        try:
            content = read_file(file_path)
            loc, funcs, lang = analyze_file_for_ast_metrics(file_path, content)

            total_loc += loc
            total_functions += funcs
            if lang != "unknown":
                languages.add(lang)

        except Exception:
            continue

    return {
        "total_loc": total_loc,
        "total_functions": total_functions,
        "total_files": total_files,
        "languages": sorted(languages)
    }
