import { createFileRoute, Outlet, useParams, useNavigate, useLocation, Link } from '@tanstack/react-router';
import { Button } from '@/components/atomic/button';

export const Route = createFileRoute('/_authenticated/project/$projectId')({
  component: RouteComponent,
})

function RouteComponent() {
  const { projectId } = useParams({ from: '/_authenticated/project/$projectId' });
  const location = useLocation();
  const navigate = useNavigate();

  // Determine active tab based on current pathname
  const getActiveTab = () => {
    const pathname = location.pathname;
    if (pathname.includes('/sbomscan')) return 'sbomscan';
    if (pathname.includes('/codescan')) return 'codescan';
    if (pathname.includes('/settings')) return 'settings';
    // Default to the overview (settings) tab if no specific tab is in URL
    return 'settings';
  };

  const activeTab = getActiveTab();

  const tabClass = (tab: string) =>
    `flex-1 py-4 px-6 text-sm font-medium transition-colors duration-200 text-center ${
      activeTab === tab ? 'bg-primary text-white border-b-2 border-primary' : ''
    }`;

  return (
    <div className="p-2">
      <div className="max-w-8xl mx-auto">
        <div className="bg-card text-card-foreground rounded-lg shadow-sm border overflow-hidden">
          {/* Go Back Button */}
          <div className="p-4 border-b">
            <Button
              variant="ghost"
              type="button"
              onClick={() => navigate({ to: '/project/list' })}
            >
              ←  Back to Project List
            </Button>
          </div>

          {/* Tab bar */}
          <div className="flex border-b">
            <Link to="/project/$projectId/settings" params={{ projectId }} className={tabClass('settings')}>
              Overview
            </Link>
            <Link to="/project/$projectId/codescan" params={{ projectId }} className={tabClass('codescan')}>
              Code Scan
            </Link>
            <Link to="/project/$projectId/sbomscan" params={{ projectId }} className={tabClass('sbomscan')}>
              SBOM Scan
            </Link>
          </div>

          {/* Content */}
          <div className="p-4">
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  );
}