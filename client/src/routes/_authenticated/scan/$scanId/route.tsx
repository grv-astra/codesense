import { Button } from '@/components/atomic/button';
import { useScanDetails } from '@/hooks/use-scans';
import { createFileRoute, Outlet, useParams, useLocation, Link, useNavigate } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/scan/$scanId')({
  component: RouteComponent,
})

function RouteComponent() {
  const { scanId } = useParams({ from: '/_authenticated/scan/$scanId' });
  const { data: scan } = useScanDetails(scanId);
  const navigate = useNavigate();
  const location = useLocation();
  
  // Determine active tab based on current pathname
  const getActiveTab = () => {
    const pathname = location.pathname;
    if (pathname.includes('/findings')) return 'findings';
    if (pathname.includes('/updates')) return 'updates';
    // Default to updates if no specific tab is in URL
    return 'updates';
  };

  const activeTab = getActiveTab();
  
  return (
    <div className="p-2">
      <Button
              variant="ghost"
              type="button"
              disabled={!scan?.project_id}
              onClick={() => {
                if (!scan?.project_id) return;
                navigate({ to: '/project/$projectId/codescan', params: { projectId: scan.project_id } });
              }}
            >
              ←  Back to Code Scan List
            </Button>
      <div className="max-w-8xl mx-auto pt-2">

        {/* Tabs */}
        <div className="bg-card text-card-foreground rounded-lg shadow-sm border overflow-hidden">
          <div className="flex border-b">
            <Link
              to="/scan/$scanId/updates"
              params={{ scanId }}
              className={`flex-1 py-4 px-6 text-sm font-medium transition-colors duration-200 text-center ${
                activeTab === 'updates'
                  ? 'bg-primary text-white border-b-2 border-primary'
                  : ''
              }`}
            >
              Updates
            </Link>
            <Link
              to="/scan/$scanId/findings"
              params={{ scanId }}
              className={`flex-1 py-4 px-6 text-sm font-medium transition-colors duration-200 text-center ${
                activeTab === 'findings'
                  ? 'bg-primary text-white border-b-2 border-primary'
                  : ''
              }`}
            >
              Findings
              {!!scan?.findings && (
                <span className="ml-2 px-2 py-1 text-xs rounded-full bg-red-100 text-primary">
                  {scan.findings}
                </span>
              )}
            </Link>
          </div>

          {/* Tab Content */}
          <div className="p-4">
            <Outlet />
          </div>
        </div>

      </div>
    </div>
  );
}