import { StateBadge } from '@/components/atomic/enum-badge';
import type { RecentScanItem } from '@/types/dashboard';
import { Link } from '@tanstack/react-router';
import { FileSearch, ScanLine } from 'lucide-react';

const timeAgo = (iso: string) => {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
};

const RecentActivity = ({ data = [] }: { data?: RecentScanItem[] }) => {
  return (
    <div className="bg-white dark:bg-[#2d2d2d] rounded-xl shadow-lg border border-gray-200 dark:border-[#444] p-6 max-w-full">
      <div style={{ marginBottom: '16px' }}>
        <div className="font-bold text-sm text-gray-900 dark:text-gray-100 transition-colors duration-300">
          Recent Activity
        </div>
        <div className="text-xs mt-0.5 text-gray-400 dark:text-gray-500 transition-colors duration-300">
          Latest code and SBOM scans across all projects
        </div>
      </div>

      {data.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-gray-500">No scans yet.</p>
      ) : (
        <div className="space-y-3">
          {data.map((scan) => {
            const Icon = scan.type === 'sbom' ? FileSearch : ScanLine;
            const linkProps = scan.type === 'sbom'
              ? { to: '/scan/sbom/$sbomscanId/updates' as const, params: { sbomscanId: scan.id } }
              : { to: '/scan/$scanId/updates' as const, params: { scanId: scan.id } };

            return (
              <Link
                key={scan.id}
                {...linkProps}
                className="flex items-center gap-3 border-b pb-2 last:border-b-0 hover:bg-gray-50 dark:hover:bg-[#1f1f1f] rounded-md -mx-1 px-1 transition-colors"
              >
                <div className="p-1.5 rounded-md bg-red-900 dark:bg-red-800 shrink-0">
                  <Icon size={14} className="text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold truncate">{scan.project}</p>
                    <StateBadge state={scan.status} size="xs" />
                  </div>
                  <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 gap-2">
                    <span className="truncate">{scan.scan_name}</span>
                    <span className="shrink-0">{scan.findings} findings · {timeAgo(scan.created_at)}</span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default RecentActivity;
