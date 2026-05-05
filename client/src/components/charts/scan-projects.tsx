import type { ScansByProjectItem } from '@/types/dashboard';

function ScanProjects({ data = [] }: { data?: ScansByProjectItem[] }) {
  return (
    <div className="bg-white dark:bg-[#2d2d2d] rounded-xl shadow-lg border border-gray-200 dark:border-[#444] p-6 max-w-full">
      <div style={{ marginBottom: '16px' }}>
        <div className="font-bold text-sm text-gray-900 dark:text-gray-100 transition-colors duration-300">
          Top Scanned Projects
        </div>
        <div className="text-xs mt-0.5 text-gray-400 dark:text-gray-500 transition-colors duration-300">
          Projects with the highest scan and finding activity
        </div>
      </div>
      <div className="space-y-3">
        {data.slice(0, 7).map((proj) => (
          <div key={proj.project} className="border-b pb-2">
            <div className="flex justify-between items-start mb-1 gap-3">
              <p className="text-sm font-semibold">{proj.project}</p>
              <span className="text-xs font-bold text-red-600 whitespace-nowrap">{proj.critical} Critical</span>
            </div>
            <div className="flex justify-between text-xs">
              <span>{proj.scans} scans</span>
              <span>{proj.findings} findings</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ScanProjects;
