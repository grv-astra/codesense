import { createFileRoute, useParams } from '@tanstack/react-router';
import { GenericTable, type TableColumn } from '@/components/molecule/generic-table';
import { useState } from 'react';
import { useSbomFindings } from '@/hooks/use-finding';
import type { SbomFindings } from '@/types/finding';
import { SecurityBadge } from '@/components/atomic/enum-badge';
import { Card } from '@/components/atomic/card';
import { Button } from '@/components/atomic/button';
import { X } from 'lucide-react';

export const Route = createFileRoute(
  '/_authenticated/scan/sbom/$sbomscanId/findings'
)({
  component: FindingsComponent,
});

function ScoreCard({ label, value }: { label: string; value?: number }) {
  return (
    <div className="rounded-xl border bg-background p-4 shadow-sm">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value ?? '—'}</p>
    </div>
  );
}

function InfoCard({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value?: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-xl border bg-background p-4 shadow-sm">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={`mt-1 text-sm font-medium ${
          highlight ? 'text-green-600 dark:text-green-400' : ''
        }`}
      >
        {value || '—'}
      </p>
    </div>
  );
}

function FindingDetailDialog({
  finding,
  onClose,
}: {
  finding: SbomFindings | null;
  onClose: () => void;
}) {
  if (!finding) return null;

  const cvss = finding.cvss?.[0];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <Card
        className="relative w-full max-w-2xl rounded-xl border shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b px-6 py-4">
          <div>
            <p className="text-base font-semibold">
              {finding.package?.name}
              <span className="ml-2 text-sm text-muted-foreground">
                ({finding.package?.version})
              </span>
            </p>
            <p className="text-xs text-muted-foreground">
              {finding.cve_id}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <SecurityBadge severity={finding.severity} />
            <Button size="icon" variant="ghost" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Body */}
        <div className="space-y-6 p-6">
          {/* Description */}
          <div>
            <p className="mb-1 text-xs uppercase text-muted-foreground">
              Description
            </p>
            <p className="text-sm">
              {finding.description || '—'}
            </p>
          </div>

          {/* CVSS */}
          {cvss && (
            <div className="grid grid-cols-3 gap-4">
              <ScoreCard label="Base Score" value={cvss.base_score} />
              <ScoreCard label="Impact Score" value={cvss.impact_score} />
              <ScoreCard
                label="Exploitability"
                value={cvss.exploitability_score}
              />
            </div>
          )}

          {/* Package Info */}
          <div className="grid grid-cols-2 gap-4">
            <InfoCard label="Package" value={finding.package?.name} />
            <InfoCard label="Type" value={finding.package?.type} />
            <InfoCard label="Installed Version" value={finding.package?.version} />
            <InfoCard
              label="Fix Versions"
              value={finding.fix_versions?.join(', ') || 'N/A'}
              highlight
            />
          </div>

          {/* CVSS Details */}
          {cvss && (
            <div className="rounded-xl border bg-muted/40 p-4">
              <p className="mb-2 text-xs uppercase text-muted-foreground">
                CVSS Details
              </p>

              <div className="mb-2 flex flex-wrap gap-3 text-xs">
                <span className="rounded bg-muted px-2 py-1">
                  Type: {cvss.type}
                </span>
                <span className="rounded bg-muted px-2 py-1">
                  Version: {cvss.version}
                </span>
              </div>

              <code className="break-all text-xs">{cvss.vector}</code>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

function FindingsComponent() {
  const findingsPerPage = 10;
  const [currentPage, setCurrentPage] = useState(1);
  const [search, setSearch] = useState('');
  const [selectedFinding, setSelectedFinding] = useState<SbomFindings | null>(null);

  const handleSearch = (q: string) => {
    setSearch(q);
    setCurrentPage(1);
  };

  const { sbomscanId } = useParams({
    from: '/_authenticated/scan/sbom/$sbomscanId/findings',
  });

  const { data: findingsResponse, isLoading, error } = useSbomFindings(
    sbomscanId,
    {
      page: currentPage,
      limit: findingsPerPage,
      search,
    }
  );

  const findings = findingsResponse?.findings || [];
  const totalFindings = findingsResponse?.pagination.total || 0;

  const findingColumns: TableColumn<SbomFindings>[] = [
    {
      key: 'srNo',
      header: 'Sr No.',
      render: (_, index: number) => index + 1,
      width: '80px',
    },
    {
      key: 'package_name',
      header: 'Package',
      render: (f) => f.package?.name,
    },
    {
      key: 'version',
      header: 'Version',
      render: (f) => f.package?.version,
    },
    {
      key: 'fix_versions',
      header: 'Fix Version',
      render: (f) => f.fix_versions?.join(', ') || '—',
    },
    {
      key: 'type',
      header: 'Type',
      render: (f) => f.package?.type,
    },
    { key: 'cve_id', header: 'CVE Id', sortable: true },
    {
      key: 'severity',
      header: 'Severity',
      render: (f) => <SecurityBadge severity={f.severity} />,
    },
  ];

  return (
    <>
      {/* Dialog */}
      <FindingDetailDialog
        finding={selectedFinding}
        onClose={() => setSelectedFinding(null)}
      />

      {/* Table */}
      <GenericTable
        data={findings}
        columns={findingColumns}
        title="Findings"
        loading={isLoading}
        error={error?.message}
        pagination={{
          enabled: true,
          pageSize: findingsPerPage,
          showInfo: true,
          showPageNumbers: true,
        }}
        totalItems={totalFindings}
        currentPage={currentPage}
        onPageChange={setCurrentPage}
        emptyMessage="No findings found"
        rowClassName={() =>
          `hover:bg-gray-50 hover:dark:bg-gray-300/10 cursor-pointer`
        }
        enableColumnFilter={true}
        filterButtonVariant="outline"
        onSearchChange={handleSearch}
        searchPlaceholder="Search vulnerabilities..."
        onRowClick={(finding) => setSelectedFinding(finding)}
      />
    </>
  );
}