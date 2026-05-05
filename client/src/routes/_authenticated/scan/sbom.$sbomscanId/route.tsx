import { Button } from '@/components/atomic/button';
import { useSbomScanDetails } from '@/hooks/use-scans';
import { createFileRoute, Outlet, useParams, useLocation, Link, useRouter } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/scan/sbom/$sbomscanId')({
  component: RouteComponent,
})

function RouteComponent() {

  const { sbomscanId } = useParams({ from: '/_authenticated/scan/sbom/$sbomscanId' });
  const { data: scan } = useSbomScanDetails(sbomscanId);
  const location = useLocation();
  const router = useRouter();
  
  // Determine active tab based on current pathname
  const getActiveTab = () => {
    const pathname = location.pathname;
    if (pathname.includes('/findings')) return 'findings';
    if (pathname.includes('/updates')) return 'updates';
    if (pathname.includes('/licenses')) return 'licenses';
    // Default to updates if no specific tab is in URL
    return 'updates';
  };

  const activeTab = getActiveTab();

  return(
    <div className="p-2">
      <Button variant="ghost" type="button" onClick={() => router.history.back()} >
        ←  Back to SBOM Scan List
      </Button>

      <div className="max-w-8xl mx-auto pt-2">
      
        {/* Tabs */}
        <div className="bg-card text-card-foreground rounded-lg shadow-sm border overflow-hidden">
          <div className="flex border-b">
            <Link
              to="/scan/sbom/$sbomscanId/updates"
              params={{ sbomscanId }}
              className={`flex-1 py-4 px-6 text-sm font-medium transition-colors duration-200 text-center ${
                activeTab === 'updates'
                  ? 'bg-primary text-white border-b-2 border-primary'
                  : ''
              }`}
            >
              Updates
            </Link>
            <Link
              to="/scan/sbom/$sbomscanId/findings"
              params={{ sbomscanId }}
              className={`flex-1 py-4 px-6 text-sm font-medium transition-colors duration-200 text-center ${
                activeTab === 'findings'
                  ? 'bg-primary text-white border-b-2 border-primary'
                  : ''
              }`}
            >
              Findings
              {scan?.vulnerabilities && (
                <span className="ml-2 px-2 py-1 text-xs rounded-full bg-red-100 text-primary">
                  {scan.vulnerabilities}
                </span>
              )}
            </Link>
            <Link
              to="/scan/sbom/$sbomscanId/licenses"
              params={{ sbomscanId }}
              className={`flex-1 py-4 px-6 text-sm font-medium transition-colors duration-200 text-center ${
                activeTab === 'licenses'
                  ? 'bg-primary text-white border-b-2 border-primary'
                  : ''
              }`}
            >
              Licenses
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
