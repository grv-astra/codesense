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

  test('renders rule_id as just its last dotted segment, not the full namespaced path', () => {
    render(
      <UpdatedFinding
        finding={
          {
            ...base,
            rule_id: 'generic.dockerfile.security.missing-user.missing-user',
          } as any
        }
      />,
    );

    expect(screen.getByText('missing-user')).toBeInTheDocument();
    expect(
      screen.queryByText(/generic\.dockerfile\.security/),
    ).not.toBeInTheDocument();
  });

  test('renders the data-flow diagram when steps are present', () => {
    render(
      <UpdatedFinding
        finding={
          {
            ...base,
            flow_diagram: [
              "Source (line 12): request.GET['q']",
              'Sink (line 18): cursor.execute(query)',
            ],
          } as any
        }
      />,
    );

    expect(screen.getByText(/Data Flow/i)).toBeInTheDocument();
    expect(screen.getByText(/request\.GET\['q'\]/)).toBeInTheDocument();
    expect(screen.getByText(/cursor\.execute\(query\)/)).toBeInTheDocument();
  });

  test('omits the data-flow section when no steps are present', () => {
    render(<UpdatedFinding finding={{ ...base, flow_diagram: [] } as any} />);
    expect(screen.queryByText(/Data Flow/i)).not.toBeInTheDocument();
  });

  test('renders line numbers and a language badge for the code snippet', () => {
    render(
      <UpdatedFinding
        finding={
          {
            ...base,
            file_path: 'app/views.py [10,12]',
            code_snip: 'a = 1\nb = 2\nc = 3',
            code_snip_start_line: 10,
          } as any
        }
      />,
    );

    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('11')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
  });

  test('falls back to unnumbered code when code_snip_start_line is absent', () => {
    render(
      <UpdatedFinding
        finding={
          {
            ...base,
            file_path: 'app/views.py [10,12]',
            code_snip: 'a = 1\nb = 2\nc = 3',
            code_snip_start_line: undefined,
          } as any
        }
      />,
    );

    expect(screen.getByText(/a = 1/)).toBeInTheDocument();
    expect(screen.queryByText('10')).not.toBeInTheDocument();
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
