// src/components/FindingList.tsx
import React, { useState } from 'react';
import { Card } from '@/components/atomic/card'; // optional – remove if unused

// ────────────────────────────────────────────────────────────────
// TYPES
// ────────────────────────────────────────────────────────────────
interface Finding {
  id: number;          // Sr No.
  name: string;        // Finding name
  severity: 'Critical' | 'High' | 'Medium' | 'Low';
  status: 'Open' | 'Close';
  valid: boolean;      // user‑controlled, starts false
}

// ────────────────────────────────────────────────────────────────
// DUMMY DATA  (48 rows → 5 pages @ 10 rows / page)
// ────────────────────────────────────────────────────────────────
const seedFindings: Finding[] = Array.from({ length: 48 }, (_, i) => ({
  id: i + 1,
  name: `Finding ${i + 1}`,
  severity:
    i % 4 === 0 ? 'Critical' :
    i % 4 === 1 ? 'High'     :
    i % 4 === 2 ? 'Medium'   : 'Low',
  status: i % 3 === 0 ? 'Close' : 'Open',
  valid : false,                     // ⇦ always starts unchecked
}));

// ────────────────────────────────────────────────────────────────
// HELPER: badge colours for severity
// ────────────────────────────────────────────────────────────────
const severityClasses: Record<Finding['severity'], string> = {
  Critical: 'bg-[#800000] text-white',
  High:     'bg-[#cc0000] text-white',
  Medium:   'bg-[#ffc000] text-white',
  Low:      'bg-[#a8d08d] text-white',
};

// ────────────────────────────────────────────────────────────────
// COMPONENT
// ────────────────────────────────────────────────────────────────
function FindingList() {
  /* ----------------------------------------------------------------
     Local state (data   + current page)
  ---------------------------------------------------------------- */
  const [findings,     setFindings]   = useState<Finding[]>(seedFindings);
  const [currentPage,  setCurrentPage] = useState<number>(1);
  const findingsPerPage = 10;

  /* ----------------------------------------------------------------
     Pagination helpers
  ---------------------------------------------------------------- */
  const totalPages = Math.ceil(findings.length / findingsPerPage);
  const idxLast    = currentPage * findingsPerPage;
  const idxFirst   = idxLast - findingsPerPage;
  const currentRows = findings.slice(idxFirst, idxLast);

  /* ----------------------------------------------------------------
     Handlers
  ---------------------------------------------------------------- */
  const toggleValid = (id: number) =>
    setFindings(prev =>
      prev.map(f => (f.id === id ? { ...f, valid: !f.valid } : f)),
    );

  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) setCurrentPage(page);
  };

  /* ----------------------------------------------------------------
     Render
  ---------------------------------------------------------------- */
  return (
    <div className="px-4">
      <h2 className="text-3xl font-bold mb-8" style={{ color: '#2d2d2d' }}>
        Findings
      </h2>

      {/* TABLE */}
      <div
        className="bg-white shadow-md overflow-hidden"
        style={{ border: '1px solid #e5e5e5' }}
      >
        <table className="w-full text-left border border-gray-200 rounded-lg">
          <thead className="bg-gray-100">
            <tr>
              <th className="px-4 py-3 border-b">Sr No.</th>
              <th className="px-4 py-3 border-b">Finding Name</th>
              <th className="px-4 py-3 border-b">Severity</th>
              <th className="px-4 py-3 border-b">Status</th>
              <th className="px-4 py-3 border-b text-center">Valid</th>
            </tr>
          </thead>

          <tbody>
            {currentRows.map((row, idx) => (
              <tr key={row.id} className="hover:bg-gray-50">
                {/* Sr No. */}
                <td className="px-4 py-3 border-b">{idxFirst + idx + 1}</td>

                {/* Name */}
                <td className="px-4 py-3 border-b">{row.name}</td>

                {/* Severity badge */}
                <td className="px-4 py-3 border-b">
                  <span
                    className={`flex justify-center w-[5rem] px-2 py-1 rounded text-sm font-semibold ${severityClasses[row.severity]}`}
                  >
                    {row.severity}
                  </span>
                </td>

                {/* Status badge */}
                <td className="px-4 py-3 border-b">
                  <span
                    className={`flex justify-center w-[4rem] px-2 py-1 rounded text-sm font-semibold ${
                      row.status === 'Open'
                        ? 'bg-red-500/20 text-red-500'
                        : 'bg-green-500/20 text-green-500'
                    }`}
                  >
                    {row.status}
                  </span>
                </td>

                {/* Valid checkbox (manual) */}
                <td className="px-4 py-3 border-b text-center">
                  <input
                    type="checkbox"
                    checked={row.valid}
                    onChange={() => toggleValid(row.id)}
                    className="w-6 h-6 accent-[#bf0000] cursor-pointer"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* PAGINATION */}
      <div className="flex flex-wrap justify-between items-center mt-6 gap-4">
        <p className="text-sm text-gray-600">
          Showing {idxFirst + 1}‑{Math.min(idxLast, findings.length)} of{' '}
          {findings.length} findings
        </p>

        <div className="flex items-center gap-2">
          {/* Previous */}
          <button
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage === 1}
            className="px-4 py-2 border text-sm rounded-lg disabled:text-gray-400 disabled:cursor-not-allowed"
          >
            &lt;&nbsp;Previous
          </button>

          {/* Page numbers */}
          {Array.from({ length: totalPages }, (_, i) => (
            <button
              key={i}
              onClick={() => goToPage(i + 1)}
              className={`w-8 h-8 text-sm rounded-md border transition ${
                currentPage === i + 1
                  ? 'bg-[#bf0000] text-white'
                  : 'bg-white text-[#2d2d2d] hover:bg-gray-100'
              }`}
            >
              {i + 1}
            </button>
          ))}

          {/* Next */}
          <button
            onClick={() => goToPage(currentPage + 1)}
            disabled={currentPage === totalPages}
            className="px-4 py-2 bg-[#bf0000] text-white text-sm rounded-lg hover:bg-red-800 disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed"
          >
            Next&nbsp;&gt;
          </button>
        </div>
      </div>
    </div>
  );
}

export default FindingList;
