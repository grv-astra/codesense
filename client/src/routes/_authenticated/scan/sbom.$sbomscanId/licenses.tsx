import { createFileRoute, useParams } from '@tanstack/react-router';
import { GenericTable, type TableColumn } from '@/components/molecule/generic-table';
import { Button } from '@/components/atomic/button';
import { X } from 'lucide-react';
import { useState } from 'react';
import { Card } from '@/components/atomic/card';
import { useSbomLicenses } from '@/hooks/use-finding';
import { useTableQueryState } from '@/hooks/use-table-query-state';
import type { LicenseFinding } from '@/types/finding';

export const Route = createFileRoute(
  '/_authenticated/scan/sbom/$sbomscanId/licenses',
)({ component: RouteComponent });

function DecisionBadge({ decision }: { decision: string }) {
  const isDeny = decision === 'deny';

  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize',
        isDeny
          ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
          : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
      ].join(' ')}
    >
      {decision}
    </span>
  );
}

function RiskBadge({ level, category }: { level?: string; category?: string }) {
  const risk = (level || '').toLowerCase();

  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium',
        risk === 'low'
          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
          : risk === 'medium'
          ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
          : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
      ].join(' ')}
    >
      {category || 'Unknown'}
    </span>
  );
}

function OsiChip({ approved }: { approved?: boolean }) {
  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium',
        approved
          ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
          : 'bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400',
      ].join(' ')}
    >
      {approved ? 'OSI Approved' : 'Not OSI'}
    </span>
  );
}

/* ───────────────── Dialog ───────────────── */

function LicenseDetailDialog({
  finding,
  onClose,
}: {
  finding: LicenseFinding | null;
  onClose: () => void;
}) {
  if (!finding) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <Card
        className="relative w-full max-w-2xl rounded-xl border border-border shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b px-6 py-4">
          <div>
            <p className="text-base font-semibold">
              {finding.package.name}
              <span className="ml-2 text-sm text-muted-foreground">
                v{finding.package.version}
              </span>
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">{finding.id}</p>
          </div>

          <div className="flex items-center gap-2">
            <DecisionBadge decision={finding.decision} />
            <Button size="icon" variant="ghost" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Body */}
        <div className="space-y-5 p-6">
          {/* Package */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Package', value: finding.package.name },
              { label: 'Type', value: finding.package.type },
              { label: 'Version', value: finding.package.version },
              { label: 'Decision', value: finding.decision },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-xl border bg-background p-3 shadow-sm">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="mt-1 text-sm font-medium capitalize">{value}</p>
              </div>
            ))}
          </div>

          {/* License */}
          <div className="rounded-xl border bg-background p-4 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">{finding.license.id}</span>
              <OsiChip approved={finding.license.osi_approved} />
            </div>

            <RiskBadge
              level={finding.license.risk_level}
              category={finding.license.risk_category}
            />

            {finding.license.reference && (
              <a
                href={finding.license.reference}
                target="_blank"
                rel="noreferrer"
                className="inline-block text-[12px] text-blue-600 underline underline-offset-2 dark:text-blue-400"
              >
                SPDX Reference
              </a>
            )}
          </div>

          {/* Locations */}
          <div>
            <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              Locations
            </p>

            <div className="space-y-1">
              {finding.locations.map((loc) => (
                <p
                  key={loc}
                  className="break-all rounded-lg bg-muted/50 px-3 py-2 font-mono text-[12px] text-muted-foreground"
                >
                  {loc}
                </p>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

/* ───────────────── Main ───────────────── */

function RouteComponent() {
  const findingsPerPage = 10;
  const { page: currentPage, search, setPage: setCurrentPage, setSearch } = useTableQueryState();
  const [selectedFinding, setSelectedFinding] = useState<LicenseFinding | null>(null);

  const handleSearch = (q: string) => {
    setSearch(q);
  };

  const { sbomscanId } = useParams({
    from: '/_authenticated/scan/sbom/$sbomscanId/licenses',
  });

  const { data: licenseResponse, isLoading, error } = useSbomLicenses(sbomscanId, {
    page: currentPage,
    limit: findingsPerPage,
    search,
  });

  const findings: LicenseFinding[] = licenseResponse?.licenses || [];
  const totalFindings = licenseResponse?.pagination.total || 0;

  const columns: TableColumn<LicenseFinding>[] = [
    {
      key: 'srNo',
      header: 'Sr No.',
      render: (_, index) => index + 1,
      width: '70px',
    },
    {
      key: 'package.name',
      header: 'Package Name',
      sortable: true,
    },
    {
      key: 'package.type',
      header: 'Type',
      sortable: true,
    },
    {
      key: 'package.version',
      header: 'Version',
      sortable: true,
    },
    {
      key: 'license.id',
      header: 'License',
      render: (f) => (
        <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-700 dark:bg-white/10 dark:text-gray-300">
          {f.license?.id || '—'}
        </span>
      ),
    },
    {
      key: 'license.risk_category',
      header: 'Risk Category',
      render: (f) => (
        <RiskBadge
          level={f.license?.risk_level}
          category={f.license?.risk_category}
        />
      ),
    },
    {
      key: 'decision',
      header: 'Decision',
      sortable: true,
      render: (f) => <DecisionBadge decision={f.decision} />,
    },
  ];

  return (
    <>
      <LicenseDetailDialog
        finding={selectedFinding}
        onClose={() => setSelectedFinding(null)}
      />

      <GenericTable
        className="overflow-x-auto max-w-[calc(100vw-340px)]"
        data={findings}
        columns={columns}
        title="License Findings"
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
        emptyMessage="No license findings found"
        rowClassName={() =>
          'cursor-pointer hover:bg-gray-50 hover:dark:bg-gray-300/10'
        }
        enableColumnFilter
        filterButtonVariant="outline"
        onSearchChange={handleSearch}
        searchPlaceholder="Search licenses..."
        initialQuery={search}
        onRowClick={(finding) => setSelectedFinding(finding)}
      />
    </>
  );
}