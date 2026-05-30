"""Top-40 programming-language registry for the LSAST scanner.

Single source of truth mapping file extensions → a canonical language, the
Semgrep/OpenGrep language id (or None when Semgrep has no analyzer), and a
coverage tier:
  strong  — Semgrep has mature security rules
  partial — Semgrep parses it + some rules / config-oriented
  none    — no Semgrep analyzer; the pipeline routes the file but cannot detect
            (reported as "no analyzer coverage", never as "clean")
Detection quality is bounded by Semgrep; this registry makes coverage explicit
and measurable (see the Phase-2 eval harness).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    name: str
    extensions: tuple
    semgrep_lang: str | None
    coverage: str  # "strong" | "partial" | "none"


# Top-40 (TIOBE/GitHub blend). Extensions are unique across the table.
LANGUAGES: list[Language] = [
    Language("python", (".py", ".pyi"), "python", "strong"),
    Language("javascript", (".js", ".jsx", ".mjs", ".cjs"), "javascript", "strong"),
    Language("typescript", (".ts", ".tsx"), "typescript", "strong"),
    Language("java", (".java",), "java", "strong"),
    Language("c", (".c", ".h"), "c", "strong"),
    Language("cpp", (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"), "cpp", "strong"),
    Language("csharp", (".cs",), "csharp", "strong"),
    Language("go", (".go",), "go", "strong"),
    Language("rust", (".rs",), "rust", "strong"),
    Language("ruby", (".rb",), "ruby", "strong"),
    Language("php", (".php", ".phtml"), "php", "strong"),
    Language("swift", (".swift",), "swift", "strong"),
    Language("kotlin", (".kt", ".kts"), "kotlin", "strong"),
    Language("scala", (".scala", ".sc"), "scala", "strong"),
    Language("solidity", (".sol",), "solidity", "partial"),
    Language("dart", (".dart",), "dart", "partial"),
    Language("lua", (".lua",), "lua", "partial"),
    Language("elixir", (".ex", ".exs"), "elixir", "partial"),
    Language("ocaml", (".ml", ".mli"), "ocaml", "partial"),
    Language("clojure", (".clj", ".cljs", ".cljc"), "clojure", "partial"),
    Language("julia", (".jl",), "julia", "partial"),
    Language("r", (".r",), "r", "partial"),
    Language("bash", (".sh", ".bash"), "bash", "partial"),
    Language("terraform", (".tf",), "terraform", "partial"),
    Language("dockerfile", (".dockerfile",), "dockerfile", "partial"),
    Language("yaml", (".yaml", ".yml"), "yaml", "partial"),
    Language("json", (".json",), "json", "partial"),
    Language("html", (".html", ".htm"), "html", "partial"),
    Language("sql", (".sql",), "generic", "partial"),
    Language("groovy", (".groovy", ".gradle"), "generic", "partial"),
    Language("perl", (".pl", ".pm"), None, "none"),
    Language("powershell", (".ps1", ".psm1"), None, "none"),
    Language("objectivec", (".m", ".mm"), None, "none"),
    Language("haskell", (".hs",), None, "none"),
    Language("erlang", (".erl", ".hrl"), None, "none"),
    Language("fsharp", (".fs", ".fsx"), None, "none"),
    Language("visualbasic", (".vb",), None, "none"),
    Language("cobol", (".cbl", ".cob"), None, "none"),
    Language("fortran", (".f90", ".f95", ".f03"), None, "none"),
    Language("assembly", (".asm", ".s"), None, "none"),
]

UNKNOWN = Language("unknown", (), None, "none")

_BY_EXT = {ext: lang for lang in LANGUAGES for ext in lang.extensions}


def language_for_path(path: str) -> Language:
    """Resolve a file path to its registry Language (UNKNOWN if unrecognized)."""
    ext = os.path.splitext(path)[1].lower()
    if not ext and os.path.basename(path).lower().startswith("dockerfile"):
        return _BY_EXT.get(".dockerfile", UNKNOWN)
    return _BY_EXT.get(ext, UNKNOWN)
