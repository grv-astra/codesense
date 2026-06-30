import type { FindingDetails } from '@/types/finding';
import { AlertTriangle, Shield, FileText, Code, Bug, CheckCircle, XCircle, AlertCircle, Clock, ExternalLink, ArrowDownUpIcon } from 'lucide-react'
import { Card } from '../atomic/card';
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

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'high':
        return 'bg-orange-100 text-orange-800 border-orange-200'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'low':
        return 'bg-green-100 text-green-800 border-green-200'
      case 'info':
        return 'bg-blue-100 text-blue-800 border-blue-200'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'open':
        return <XCircle className="w-5 h-5 text-red-500" />
      case 'resolved':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'closed':
        return <CheckCircle className="w-5 h-5 text-gray-500" />
      case 'in-progress':
        return <Clock className="w-5 h-5 text-yellow-500" />
      case 'false-positive':
        return <AlertCircle className="w-5 h-5 text-blue-500" />
      default:
        return <AlertCircle className="w-5 h-5 text-gray-500" />
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

  return (
    <Card className="overflow-auto p-0">
      <div className="rounded-lg shadow-lg border">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 rounded-t-lg">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Bug className="w-6 h-6 text-primary" />
              {currentFinding.title}
            </h1>
            <div className="flex items-center gap-3">
              <span className={`flex px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(currentFinding.status)}`}>
                {getStatusIcon(currentFinding.status)}
                <span className="ml-2">{currentFinding.status}</span>
              </span>
              {currentFinding.approved && (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 border border-green-200">
                  <CheckCircle className="w-4 h-4 inline mr-1" />
                  Approved
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Finding Title and Metadata */}  
          <div className="flex justify-between items-start">
            <div className='flex gap-3 flex-1'>
              <div className="flex-1">  
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <span className="bg-gray-100 px-2 py-1 rounded">
                    Finding Code: {currentFinding.code}
                  </span>
                  <span className="bg-gray-100 px-2 py-1 rounded">
                    CVSS Score: {currentFinding.cvss_score}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-end gap-2">
              <span className={`px-3 py-1 rounded-full text-sm font-medium border ${getSeverityColor(currentFinding.severity)}`}>
                {currentFinding.severity.toUpperCase()} Severity
              </span>
              <span className="text-sm text-gray-600 bg-gray-100 px-2 py-1 rounded">
                {currentFinding.cwe}
              </span>
            </div>
          </div>

        <div className="flex justify-between items-start gap-3">
          <div className='space-y-6'>
          {/* CVSS Vector */}
          <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">
              <Shield className="w-5 h-5 text-primary" />
              CVSS Vector
            </h3>
            <code className="text-primary bg-gray-300 dark:bg-gray-900/50 px-2 py-1 rounded text-sm">
              {currentFinding.cvss_vector}
            </code>
          </div>

          {/* Description */}
          <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">
              <FileText className="w-5 h-5 text-primary" />
              Description
            </h3>
            <p className="leading-relaxed text-gray-700 dark:text-gray-300">
              {currentFinding.description}
            </p>
          </div>

          {/* File Information */}
          {currentFinding.file_path && (
            <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">
                <FileText className="w-5 h-5 text-primary" />
                Affected File
              </h3>
              <code className="text-primary bg-gray-300 dark:bg-gray-900/50 px-2 py-1 rounded text-sm">
                {currentFinding.file_path}
              </code>
            </div>
          )}

          {/* Vulnerable Code */}
          {currentFinding.code_snip && (
            <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">
                <Code className="w-5 h-5 text-primary" />
                Code Snippet
              </h3>
              <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                <pre className="text-sm text-green-400 dark:text-green-300 font-mono whitespace-pre-wrap">
                  <code>{formatCodeSnippet(currentFinding.code_snip)}</code>
                </pre>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2 mb-6">
            {/* Security Risk */}
            <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">
                <AlertTriangle className="w-5 h-5 text-primary" />
                Security Risk
              </h3>
              <div className="space-y-2 text-gray-700 dark:text-gray-300">
                {formatMitigation(currentFinding.security_risk)}
              </div>
            </div>

            {/* Mitigation (LLM remediation — empty on fail-open findings) */}
            {currentFinding.mitigation && (
              <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
                <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">
                  <Shield className="w-5 h-5 text-primary" />
                  Mitigation Steps
                </h3>
                <div className="space-y-2 text-gray-700 dark:text-gray-300">
                  {formatMitigation(currentFinding.mitigation)}
                </div>
              </div>
            )}
          </div>

          {/* Verifier Verdict (LLM confidence + reason; null = fail-open, render nothing) */}
          {currentFinding.confidence != null && (
            <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">
                <CheckCircle className="w-5 h-5 text-primary" />
                Verifier Verdict
              </h3>
              <div className="space-y-2 text-gray-700 dark:text-gray-300">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600 dark:text-gray-300">Confidence:</span>
                  <span className="font-semibold">{Math.round(currentFinding.confidence * 100)}%</span>
                </div>
                {currentFinding.verifier_reason && (
                  <p className="leading-relaxed">{currentFinding.verifier_reason}</p>
                )}
                {currentFinding.rule_id && (
                  <code className="text-primary bg-gray-300 dark:bg-gray-900/50 px-2 py-1 rounded text-xs">
                    {currentFinding.rule_id}
                  </code>
                )}
              </div>
            </div>
          )}

          {/* CWE Reference (deterministic link derived from finding.cwe) */}
          {cweNum && (
            <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">
                <ExternalLink className="w-5 h-5 text-primary" />
                CWE Reference
              </h3>
              <a
                href={`https://cwe.mitre.org/data/definitions/${cweNum}.html`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-red-600 hover:text-red-800 underline flex items-center gap-1"
              >
                {currentFinding.cwe}
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          )}

          {/* Reference Link */}
          {currentFinding.reference && (
            <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">
                <ExternalLink className="w-5 h-5 text-primary" />
                Reference
              </h3>
              <a 
                href={currentFinding.reference}
                target="_blank"
                rel="noopener noreferrer"
                className="text-red-600 hover:text-red-800 underline flex items-center gap-1"
              >
                {currentFinding.reference}
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          )}

          {/* Metadata */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Creation Date */}
            <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">
                <Clock className="w-5 h-5 text-primary" />
                Created
              </h3>
              <p className="text-gray-700 dark:text-gray-300">
                {new Date(currentFinding.created_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </p>
            </div>

            {/* Additional Metadata */}
            <div className="bg-gray-500/10 dark:bg-gray-500/20 rounded-lg p-4 border border-gray-200 dark:border-gray-500/40">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-gray-900 dark:text-[#e5e5e5]">Metadata</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-300">Finding ID:</span>
                  <span className="text-gray-900 dark:text-gray-200 font-mono">{currentFinding.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-300">Scan ID:</span>
                  <span className="text-gray-900 dark:text-gray-200 font-mono">{currentFinding.scan_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-300">Created By:</span>
                  <span className="text-gray-900 dark:text-gray-200 font-mono">{currentFinding.created_by}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-300">Deleted:</span>
                  <span className={`${currentFinding.deleted ? 'text-red-600' : 'text-green-600'}`}>
                    {currentFinding.deleted ? 'Yes' : 'No'}
                  </span>
                </div>
              </div>
            </div>
          </div>
          </div>

          </div>
        </div>
      </div>
    </Card>
  )
}

export default Finding