import { createFileRoute, Outlet, useParams, useNavigate, useLocation, useRouter } from '@tanstack/react-router';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/atomic/select";
import { Button } from '@/components/atomic/button';

export const Route = createFileRoute('/_authenticated/project/$projectId')({
  component: RouteComponent,
})

function RouteComponent() {
  const { projectId } = useParams({ from: '/_authenticated/project/$projectId' });
  const location = useLocation();
  const navigate = useNavigate();
  const router = useRouter();
  
  // Determine active tab based on current pathname
  const getActiveTab = () => {
    const pathname = location.pathname;
    if (pathname.includes('/sbomscan')) return 'sbomscan';
    if (pathname.includes('/codescan')) return 'codescan';
    // Default to codescan if no specific tab is in URL
    return 'codescan';
  };

  const activeTab = getActiveTab();

  const handleScanTypeChange = (value: string) => {
    navigate({
      to: `/project/$projectId/${value}`,
      params: { projectId }
    });
  };

  return (
    <div className="p-2">
      <div className="max-w-8xl mx-auto">
        {/* Select Dropdown */}
        <div className="bg-card text-card-foreground rounded-lg shadow-sm border overflow-hidden">
          <div className="p-4 border-b flex items-center justify-between">
            {/* Go Back Button (Left) */}
            <Button
              variant="ghost"
              type="button"
              onClick={() => router.history.back()}
            >
              ←  Back to Project List
            </Button>
            
              {/* <label htmlFor="scan-type" className="block text-sm font-medium mb-2">
                Select Scan Type
              </label> */}
              <Select value={activeTab} onValueChange={handleScanTypeChange}>
                <SelectTrigger className="w-xl">
                  <SelectValue placeholder="Select scan type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="codescan">Code Scan</SelectItem>
                  <SelectItem value="sbomscan">SBOM Scan</SelectItem>
                </SelectContent>
              </Select>
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