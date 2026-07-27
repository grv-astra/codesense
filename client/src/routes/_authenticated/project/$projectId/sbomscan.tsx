import { createFileRoute, useNavigate, useParams } from '@tanstack/react-router';
import { GenericTable, type TableColumn } from '@/components/molecule/generic-table';
import { Button } from '@/components/atomic/button';
import { Download, Trash2 } from 'lucide-react';
import { useDeleteSbomScan, useScans } from '@/hooks/use-scans';
import type { SbomScanDetails } from '@/types/scan';
import { StateBadge } from '@/components/atomic/enum-badge';
import { scanService } from '@/services/scan.service';
import { formatTimestamp } from '@/utils/timestampFormater';
import { AxiosError } from 'axios';
import { toast } from 'sonner';
import { ConfirmDialog } from '@/components/atomic/dialog-confirm';
import { useTableQueryState } from '@/hooks/use-table-query-state';

export const Route = createFileRoute(
  '/_authenticated/project/$projectId/sbomscan',
)({
  component: RouteComponent,
})

function RouteComponent() {

  const navigate = useNavigate()
  const scansPerPage = 10;
  const { page: currentPage, search, setPage: setCurrentPage, setSearch } = useTableQueryState();
  const { projectId } = useParams({ from: '/_authenticated/project/$projectId/sbomscan' });

  const handleSearch = (q: string) => {
    setSearch(q);
  };

  // For server-side pagination
  const { data: scanResponse, isLoading, error } = useScans(projectId, {
    type: "sbom",
    page: currentPage,
    limit: scansPerPage,
    search,
  });
  const deleteScanMutation = useDeleteSbomScan()

  const scans = scanResponse?.scans || [];
  const totalScans = scanResponse?.pagination.total || 0;
  
  const scanColumns: TableColumn<SbomScanDetails>[] = [
    {
      key: 'srNo',
      header: 'Sr No.',
      render: (_, index: number) => index + 1,
      width: '80px'
    },
    {
      key: 'scan_name',
      header: 'Scan Name',
      sortable: true
    },
    {
      key: 'status',
      header: 'Status',
      render: (scan) => (
        <StateBadge state={scan.status} />
      )
    },
    {
      key: 'vulnerabilities',
      header: 'Total Findings',
    },
    {
      key: 'created_at',
      header: 'Started At',
      render: (scan) => (
        <p>{formatTimestamp(scan.created_at)}</p>
      )
    },
    {
      key: 'end_time',
      header: 'Ended At',
      render: (scan) => (
        <p>{formatTimestamp(scan.end_time)}</p>
      )
    },
    {
      key: 'download_csv',
      header: 'Export Findings',
      render: (scan) => (
        <Button
          size="sm"
          variant="outline"
          onClick={(e) => {
            e.stopPropagation();
            handleDownloadCSV(scan);
          }}
          className="text-red-600 hover:text-red-700"
        >
          <Download className="w-4 h-4">CSV</Download>
        </Button>
      )
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (scan) => (
        <div className="flex space-x-2">
          <ConfirmDialog
            trigger={
              <Button size="sm" variant="outline" className="text-red-600 hover:text-red-700">
                <Trash2 className="w-4 h-4" />
              </Button>
            }
            title="Delete Scan"
            description="This action cannot be undone. The scan and its findings will be permanently deleted."
            confirmLabel="Delete"
            cancelLabel="Cancel"
            confirmText={scan.scan_name}    // 👈 require typing scan name
            onConfirm={() => handleDelete(scan)}
          />
        </div>
      ),
      width: '150px'
    }
  ];

  const handleDownloadCSV = async (scan: SbomScanDetails) => {
    try {
      const response = await scanService.downloadSbomCsv(scan.id)
      const blob = new Blob([response.data], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${scan.scan_name}_findings.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast("Download failed", {
        description: "Could not export findings. Please try again.",
      });
    }
  }

  const handleDelete = async (scan: SbomScanDetails) => {
    try {
      await deleteScanMutation.mutateAsync(scan.id)
    } catch (error) {
      if (error instanceof AxiosError && error.response) {
        toast("Request Failed", {
          description: error.response.data.detail,
        });
      } else {
        toast("Request Failed", {
          description: "An unexpected error occurred",
        });
      }
    }
    
  };

  const handleRowClick = (scan: SbomScanDetails) => {
    navigate({from: '/project/$projectId', to: `/scan/sbom/${scan.id}`})
  };

  return(
    <GenericTable
      data={scans}
      columns={scanColumns}
      title="SBOM Scans List"
      loading={isLoading}
      error={error?.message}
      pagination={{
        enabled: true,
        pageSize: scansPerPage,
        showInfo: true,
        showPageNumbers: true
      }}
      totalItems={totalScans}
      currentPage={currentPage}
      onPageChange={setCurrentPage}
      emptyMessage="No projects found"
      onRowClick={handleRowClick}
      rowClassName={() =>
        `hover:bg-gray-50 hover:dark:bg-gray-300/10`
      }
      onSearchChange={handleSearch}
      searchPlaceholder="Search scans..."
      initialQuery={search}
    />
  );
}
