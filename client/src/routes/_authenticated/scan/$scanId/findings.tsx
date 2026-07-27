import { createFileRoute, useNavigate, useParams } from '@tanstack/react-router';
import { GenericTable, type TableColumn } from '@/components/molecule/generic-table';
import { Button } from '@/components/atomic/button';
import { Eye, Trash2 } from 'lucide-react';
import { useDeleteFinding, useFindings, useToggleFindingApproved } from '@/hooks/use-finding';
import type { FindingDetails } from '@/types/finding';
import { SecurityBadge, StatusBadge } from '@/components/atomic/enum-badge';
import { useTableQueryState } from '@/hooks/use-table-query-state';

export const Route = createFileRoute('/_authenticated/scan/$scanId/findings')({
  component: FindingsComponent,
});

function FindingsComponent() {
  const navigate = useNavigate();
  const findingsPerPage = 10;
  const { page: currentPage, search, setPage: setCurrentPage, setSearch } = useTableQueryState();
  const { scanId } = useParams({ from: '/_authenticated/scan/$scanId/findings' });

  const handleSearch = (q: string) => {
    setSearch(q);
  };

  // Queries
  const { data: findingsResponse, isLoading, error } = useFindings(scanId, {
    page: currentPage,
    limit: findingsPerPage,
    search,
  });

  const toggleFindingApproved = useToggleFindingApproved();
  const deleteFindingMutation = useDeleteFinding();

  const findings = findingsResponse?.findings || [];
  const totalFindings = findingsResponse?.pagination.total || 0;

  const toggleValid = (finding: FindingDetails) => {
    toggleFindingApproved.mutate(finding.id);
  };

  const handleEdit = (finding: FindingDetails) => {
    navigate({
      from: '/scan/$scanId/findings',
      to: `/finding/${finding.id}`,
    });
  };

  const handleDelete = async (finding: FindingDetails) => {
    try {
      await deleteFindingMutation.mutateAsync(finding.id)
    } catch (error) {
      console.error("error: "+ error)
    }
  };

  const findingColumns: TableColumn<FindingDetails>[] = [
    {
      key: 'srNo',
      header: 'Sr No.',
      render: (_, index: number) => index + 1,
      width: '80px',
    },
    {
      key: 'title',
      header: 'Finding Name',
      sortable: true,
    },
    {
      key: 'status',
      header: 'Status',
      render: (finding) => <StatusBadge status={finding.status} />,
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (finding) => <SecurityBadge severity={finding.severity} />,
    },
    {
      key: 'approved',
      header: 'Valid',
      render: (finding) => (
        <input
          type="checkbox"
          checked={finding.approved}
          onChange={() => toggleValid(finding)}
          className="w-6 h-6 accent-[#bf0000] cursor-pointer"
          disabled={toggleFindingApproved.isPending && toggleFindingApproved.variables === finding.id}
        />
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (finding) => (
        <div className="flex space-x-2">
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              handleEdit(finding);
            }}
          >
            <Eye className="w-4 h-4" />
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              handleDelete(finding);
            }}
            className="text-red-600 hover:text-red-700"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      ),
      width: '150px',
    },
  ];

  return (
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
        `hover:bg-gray-50 hover:dark:bg-gray-300/10`
      }
      enableColumnFilter={true}
      filterButtonVariant="outline"
      onSearchChange={handleSearch}
      searchPlaceholder="Search findings..."
      initialQuery={search}
    />
  );
}
