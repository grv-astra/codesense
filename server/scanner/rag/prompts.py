def create_enhanced_prompt(
    chunk: str,
    file_name: str,
    file_extension: str,
    risk_signals: list[str] | None = None,
) -> str:
    """
    Build a prompt matched to the model's natural output style.

    Key findings from live model testing:
    - The model is a FIM (fill-in-the-middle) model used via chat endpoint.
    - It does NOT follow a system prompt — ignore system role entirely.
    - It naturally produces the structured format when the user message
      ends with the code block and file name, matching its training data.
    - It echoes the prompt before answering — _clean_output() strips this.
    - Keep the prompt SHORT: this model has a 4096 token context but the
      structured output itself consumes ~150-200 tokens, so input budget
      is roughly 3800 tokens (~13000 chars).  We target <1000 chars here.
    """
    signal_text = (
        ", ".join(risk_signals)
        if risk_signals else "none"
    )

    # Minimal, direct format — matches the model's training data structure.
    # No verbose headers, no example placeholders, no padding.
    return (
        f"Analyze the following {file_extension} code for security vulnerabilities.\n"
        f"Risk indicators detected: {signal_text}.\n"
        f"If vulnerable, respond in this format:\n"
        f"Vulnerability: <name>\n"
        f"CWE: <CWE-XXX>\n"
        f"Severity: <Critical|High|Medium|Low>\n"
        f"Impact: <what attacker achieves>\n"
        f"Mitigation: <specific fix>\n"
        f"Affected: <function or line>\n"
        f"Code Snippet:\n"
        f"<exact vulnerable code>\n\n"
        f"If no real vulnerability exists, respond: NO_VULNERABILITY_FOUND\n\n"
        f"```{file_extension}\n{chunk}\n```\n"
        f"File: {file_name}"
    )