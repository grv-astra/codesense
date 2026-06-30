import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import UpdatedFinding from './UpdatedFinding';

// Minimal finding shape (cast as any — the component only reads a subset).
const base = {
  title: 'node-mysql-sqli',
  cwe: 'CWE-89',
  severity: 'high',
  description: 'd',
  security_risk: 'r',
  mitigation: 'use params',
  confidence: 0.82,
  verifier_reason: 'tainted concat',
  rule_id: 'x.sqli',
};

describe('UpdatedFinding', () => {
  test('renders remediation + cwe link + confidence when present', () => {
    render(<UpdatedFinding finding={base as any} />);

    // LLM remediation
    expect(screen.getByText(/use params/)).toBeInTheDocument();
    // Verifier confidence rendered as a percentage (0.82 -> 82%)
    expect(screen.getByText(/82%/)).toBeInTheDocument();
    // Verifier reason
    expect(screen.getByText(/tainted concat/)).toBeInTheDocument();
    // CWE reference link to cwe.mitre.org (deterministic, derived from finding.cwe)
    const cweLink = screen.getByRole('link', { name: /CWE-89/i });
    expect(cweLink).toHaveAttribute(
      'href',
      'https://cwe.mitre.org/data/definitions/89.html',
    );
  });

  test('renders without optional/empty fields (fail-open finding)', () => {
    render(
      <UpdatedFinding
        finding={
          {
            ...base,
            confidence: undefined,
            verifier_reason: undefined,
            mitigation: '',
          } as any
        }
      />,
    );

    // Still renders the title without crashing
    expect(screen.getByText(/node-mysql-sqli/)).toBeInTheDocument();
    // Verifier block is absent when confidence is undefined/null (fail-open default)
    expect(screen.queryByText(/82%/)).not.toBeInTheDocument();
  });
});
