import type { FindingDetails } from '@/types/finding';
import { AlertTriangle, Shield, FileText, Code, Bug, CheckCircle, XCircle, AlertCircle, Clock, ExternalLink, ArrowDownUpIcon, Info } from 'lucide-react'
import { Card } from '../atomic/card';
import { SecurityBadge } from '../atomic/enum-badge';
import React from 'react';

interface FindingProps {
  finding?: FindingDetails;
}

function Finding({ finding }: FindingProps) {
  // Sample finding data - replace with your actual data source
  const defaultFinding: FindingDetails = {
    id: "6895a61bfd752429c18740bc",
    scan_id: "6895a4aafd752429c18740bb",
    created_by: "68863cf8ee93d4964a00d585",
    cwe: "CWE-22 - Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')",
    cvss_vector: "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:L",
    cvss_score: "6.5",
    code: "f-8bb903db",
    title: "Path Traversal",
    description: "This proof of concept demonstrates how path traversal can occur. The vulnerability allows an attacker to access files outside the intended directory, potentially leading to sensitive data disclosure or modification.",
    severity: "medium",
    file_path: "index.html",
    code_snip: "```py\ncv = Converter(pdf_file)  # Convert the PDF to DOCX\ncv.convert(docx_file, start=0, end=None)  # Convert all pages\n```",
    security_risk: "The vulnerability allows an attacker to access files outside the intended directory, potentially leading to sensitive data disclosure or modification.",
    mitigation: "Use the `os.path.join()` function to concatenate paths and avoid using string manipulation to construct file paths. Additionally, ensure that all user-supplied input is properly sanitized and validated before being used in a file path.",
    status: "open",
    deleted: false,
    approved: false,
    reference: "https://cwe.mitre.org/data/definitions/22.html",
    created_at: "2025-08-08T07:24:11.678000",
  };

  const currentFinding = finding || defaultFinding;

  // Severity accent shown as a top border strip on the whole card, so the
  // overall risk level is visible before reading anything else.
  const SEVERITY_ACCENT: Record<string, string> = {
    critical: 'border-t-red-600',
    high: 'border-t-orange-500',
    medium: 'border-t-yellow-500',
    low: 'border-t-green-500',
    info: 'border-t-blue-500',
  };
  const accentClass = SEVERITY_ACCENT[currentFinding.severity?.toLowerCase()] || 'border-t-gray-400';

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'open':
        return <XCircle className="w-4 h-4 text-red-500" />
      case 'resolved':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'closed':
        return <CheckCircle className="w-4 h-4 text-gray-500" />
      case 'in-progress':
        return <Clock className="w-4 h-4 text-yellow-500" />
      case 'false-positive':
        return <AlertCircle className="w-4 h-4 text-blue-500" />
      default:
        return <AlertCircle className="w-4 h-4 text-gray-500" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'open':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'resolved':
        return 'bg-green-100 text-green-800 border-green-200'
      case 'closed':
        return 'bg-gray-100 text-gray-800 border-gray-200'
      case 'in-progress':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'false-positive':
        return 'bg-blue-100 text-blue-800 border-blue-200'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const formatMitigation = (mitigation: string) => {
    return mitigation.split('\n').map((line, index) => (
      <div key={index} className="mb-2 last:mb-0">
        {line}
      </div>
    ))
  }

  const formatCodeSnippet = (codeSnip: string) => {
    // Remove markdown code block markers if present
    const cleanCode = codeSnip.replace(/^```\w*\n?/, '').replace(/\n?```$/, '');
    return cleanCode;
  }

  // Extract the numeric id from a deterministic CWE label (e.g. "CWE-89 - SQLi" -> "89")
  // so we can build a canonical cwe.mitre.org reference link.
  const cweNumber = (cwe?: string): string | null => {
    const match = cwe?.match(/CWE[-\s]?(\d+)/i);
    return match ? match[1] : null;
  }
  const cweNum = cweNumber(currentFinding.cwe);
  const hasFlowDiagram = !!currentFinding.flow_diagram && currentFinding.flow_diagram.length > 0;

  // file_path carries a trailing " [start,end]" line-range suffix (see
  // finding_normalizer.normalize) — strip it to get the real path for
  // extension-based language detection.
  const LANGUAGE_BY_EXT: Record<string, string> = {
    py: 'Python', js: 'JavaScript', jsx: 'JavaScript', mjs: 'JavaScript', cjs: 'JavaScript',
    ts: 'TypeScript', tsx: 'TypeScript',
    java: 'Java', php: 'PHP', go: 'Go', rb: 'Ruby',
    cs: 'C#', kt: 'Kotlin', kts: 'Kotlin',
    rs: 'Rust', c: 'C', h: 'C', cpp: 'C++', hpp: 'C++', cc: 'C++',
    yml: 'YAML', yaml: 'YAML', json: 'JSON', toml: 'TOML',
    sh: 'Shell', bash: 'Shell', sql: 'SQL', html: 'HTML', css: 'CSS',
  };
  const detectLanguage = (filePath?: string): string | null => {
    if (!filePath) return null;
    const cleanPath = filePath.replace(/\s*\[\d+,\d+\]\s*$/, '').trim();
    const base = cleanPath.split(/[\\/]/).pop() || '';
    if (/^dockerfile$/i.test(base)) return 'Dockerfile';
    const dot = base.lastIndexOf('.');
    if (dot <= 0) return null;
    return LANGUAGE_BY_EXT[base.slice(dot + 1).toLowerCase()] || null;
  };
  const codeLanguage = detectLanguage(currentFinding.file_path);

  // Numbered code block — falls back to plain (unnumbered) text on
  // pre-existing rows that have no code_snip_start_line.
  const renderCodeSnippet = (codeSnip: string, startLine?: number | null) => {
    const clean = formatCodeSnippet(codeSnip);
    if (!startLine) {
      return (
        <pre className="text-sm text-green-400 dark:text-green-300 font-mono whitespace-pre-wrap">
          <code>{clean}</code>
        </pre>
      );
    }
    const lines = clean.split('\n');
    return (
      <table className="text-sm font-mono w-full border-separate border-spacing-0">
        <tbody>
          {lines.map((line, i) => (
            <tr key={i}>
              <td className="pr-4 text-gray-500 dark:text-gray-500 select-none text-right align-top whitespace-nowrap">
                {startLine + i}
              </td>
              <td className="text-green-400 dark:text-green-300 whitespace-pre-wrap align-top w-full">
                {line}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  const renderFlowDiagram = (steps: string[]) => {
    if (!steps || steps.length === 0) return null;

    return (
      <div className="flex flex-col items-center gap-2 py-2 px-6">
        {steps.map((step, index) => (
          <React.Fragment key={index}>
            <div className="bg-gray-900/30  rounded px-4 py-2 text-center w-full">
              <span className="text-red-800 font-medium text-md break-words">
                {step}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div className="flex flex-col items-center">
                <div className="w-0.5 h-4 bg-red-800"></div>
                <div className="w-0 h-0 border-l-4 border-r-4 border-t-8 border-l-transparent border-r-transparent border-t-red-800"></div>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    );
  };

  // Small uppercase section label — used throughout the main column so each
  // block reads at a glance without a full bordered card around every field.
  const SectionLabel = ({ icon: Icon, children }: { icon: React.ElementType; children: React.ReactNode }) => (
    <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2 flex items-center gap-2">
      <Icon className="w-4 h-4" />
      {children}
    </h3>
  );

  return (
    <Card className="overflow-auto p-0">
      <div className={`rounded-lg shadow-lg border border-t-4 ${accentClass}`}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Bug className="w-6 h-6 text-primary" />
              {currentFinding.title}
            </h1>
            <div className="flex items-center gap-2 flex-wrap">
              <SecurityBadge severity={currentFinding.severity} size="md" />
              <span className={`flex items-center px-3 py-1 rounded-full text-sm font-medium border capitalize ${getStatusColor(currentFinding.status)}`}>
                {getStatusIcon(currentFinding.status)}
                <span className="ml-2">{currentFinding.status?.replace(/_/g, ' ')}</span>
              </span>
              {currentFinding.approved && (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 border border-green-200">
                  <CheckCircle className="w-4 h-4 inline mr-1" />
                  Approved
                </span>
              )}
            </div>
          </div>
          {/* Quick-glance chips: code, CVSS score, CWE */}
          <div className="flex items-center gap-2 mt-3 flex-wrap text-xs">
            <span className="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-2 py-1 rounded font-mono">
              {currentFinding.code}
            </span>
            <span className="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-2 py-1 rounded">
              CVSS {currentFinding.cvss_score}
            </span>
            <span className="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-2 py-1 rounded">
              {currentFinding.cwe}
            </span>
          </div>
        </div>

        {/* Content: main column (the reading path) + a compact details sidebar */}
        <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          <div className={`space-y-6 ${hasFlowDiagram ? 'lg:col-span-2' : 'lg:col-span-3'}`}>
            {/* Description */}
            <section>
              <SectionLabel icon={FileText}>Description</SectionLabel>
              <p className="leading-relaxed text-gray-700 dark:text-gray-300">
                {currentFinding.description}
              </p>
            </section>

            {/* Vulnerable Code (file path + detected language shown above the block) */}
            {currentFinding.code_snip ? (
              <section>
                <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
                  <SectionLabel icon={Code}>Vulnerable Code</SectionLabel>
                  {codeLanguage && (
                    <span className="text-xs bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 px-2 py-0.5 rounded">
                      {codeLanguage}
                    </span>
                  )}
                </div>
                {currentFinding.file_path && (
                  <code className="block text-xs text-gray-500 dark:text-gray-400 mb-2 break-all">
                    {currentFinding.file_path}
                  </code>
                )}
                <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                  {renderCodeSnippet(currentFinding.code_snip, currentFinding.code_snip_start_line)}
                </div>
              </section>
            ) : currentFinding.file_path && (
              <section>
                <SectionLabel icon={FileText}>Affected File</SectionLabel>
                <code className="text-primary bg-gray-300 dark:bg-gray-900/50 px-2 py-1 rounded text-sm break-all">
                  {currentFinding.file_path}
                </code>
              </section>
            )}

            {/* Security Risk */}
            <section>
              <SectionLabel icon={AlertTriangle}>Security Risk</SectionLabel>
              <div className="space-y-2 text-gray-700 dark:text-gray-300">
                {formatMitigation(currentFinding.security_risk)}
              </div>
            </section>

            {/* Mitigation (LLM remediation — empty on fail-open findings) */}
            {currentFinding.mitigation && (
              <section className="bg-green-500/5 dark:bg-green-500/10 rounded-lg p-4 border border-green-200 dark:border-green-500/30">
                <SectionLabel icon={Shield}>Mitigation Steps</SectionLabel>
                <div className="space-y-2 text-gray-700 dark:text-gray-300">
                  {formatMitigation(currentFinding.mitigation)}
                </div>
              </section>
            )}

            {/* Details — everything you'd look up rather than read, kept together
                at the end of the main reading path. */}
            <section className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
              <SectionLabel icon={Info}>Details</SectionLabel>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {currentFinding.cvss_vector && (
                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">CVSS Vector</div>
                    <code className="block text-primary bg-gray-300 dark:bg-gray-900/50 px-2 py-1 rounded text-xs break-all">
                      {currentFinding.cvss_vector}
                    </code>
                  </div>
                )}

                {/* Verifier Verdict (LLM confidence + reason; null = fail-open, render nothing) */}
                {currentFinding.confidence != null && (
                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Verifier Confidence</div>
                    <span className="font-semibold text-gray-900 dark:text-gray-100">
                      {Math.round(currentFinding.confidence * 100)}%
                    </span>
                    {currentFinding.verifier_reason && (
                      <p className="text-sm text-gray-700 dark:text-gray-300 mt-1 leading-relaxed">
                        {currentFinding.verifier_reason}
                      </p>
                    )}
                    {currentFinding.rule_id && (
                      <code className="block text-primary bg-gray-300 dark:bg-gray-900/50 px-2 py-1 rounded text-xs mt-1 break-all">
                        {currentFinding.rule_id}
                      </code>
                    )}
                  </div>
                )}

                {cweNum && (
                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">CWE Reference</div>
                    <a
                      href={`https://cwe.mitre.org/data/definitions/${cweNum}.html`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-red-600 hover:text-red-800 underline flex items-center gap-1 text-sm"
                    >
                      {currentFinding.cwe}
                      <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                    </a>
                  </div>
                )}

                {currentFinding.reference && (
                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Reference</div>
                    <a
                      href={currentFinding.reference}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-red-600 hover:text-red-800 underline flex items-center gap-1 text-sm break-all"
                    >
                      {currentFinding.reference}
                      <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                    </a>
                  </div>
                )}

                <div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Created</div>
                  <p className="text-sm text-gray-700 dark:text-gray-300">
                    {new Date(currentFinding.created_at).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 mt-4 pt-3 border-t border-gray-200 dark:border-gray-500/40 text-xs">
                <div className="flex justify-between gap-2">
                  <span className="text-gray-600 dark:text-gray-300 shrink-0">Finding ID</span>
                  <span className="font-mono text-gray-900 dark:text-gray-200 truncate">{currentFinding.id}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-gray-600 dark:text-gray-300 shrink-0">Scan ID</span>
                  <span className="font-mono text-gray-900 dark:text-gray-200 truncate">{currentFinding.scan_id}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-gray-600 dark:text-gray-300 shrink-0">Created By</span>
                  <span className="font-mono text-gray-900 dark:text-gray-200 truncate">{currentFinding.created_by}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-gray-600 dark:text-gray-300 shrink-0">Deleted</span>
                  <span className={currentFinding.deleted ? 'text-red-600' : 'text-green-600'}>
                    {currentFinding.deleted ? 'Yes' : 'No'}
                  </span>
                </div>
              </div>
            </section>
          </div>

          {/* Right column — Data Flow only (variable length, so it lives on its
              own rather than interrupting the main reading path). */}
          {hasFlowDiagram && (
            <aside className="lg:col-span-1 lg:sticky lg:top-4 lg:self-start">
              {/* Capped height + internal scroll so a long trace (many intermediate
                  steps) can't blow out the page. */}
              <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
                <SectionLabel icon={ArrowDownUpIcon}>
                  Data Flow ({currentFinding.flow_diagram.length} nodes)
                </SectionLabel>
                <div className="max-h-[28rem] overflow-y-auto">
                  {renderFlowDiagram(currentFinding.flow_diagram)}
                </div>
              </div>
            </aside>
          )}
        </div>
      </div>
    </Card>
  )
}

export default Finding
