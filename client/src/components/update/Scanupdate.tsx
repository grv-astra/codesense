import { useState, useEffect } from 'react';
import { Clock, Calendar, Shield, CheckCircle, AlertTriangle, Activity, Code, Layers, PauseCircle, XCircle } from 'lucide-react';
import { AxiosError } from 'axios';
import { toast } from 'sonner';
import { formatTimestamp } from '@/utils/timestampFormater';
import type { ScanDetails } from '@/types/scan';
import { Button } from '@/components/atomic/button';
import { ConfirmDialog } from '@/components/atomic/dialog-confirm';
import { SecurityBadge } from '@/components/atomic/enum-badge';
import { useCancelScan, useResumeScan } from '@/hooks/use-scans';

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low'] as const;

function formatDuration(scan: ScanDetails): string {
  if (!scan.created_at) return '—';
  // Only a running scan can legitimately use "now" as the end boundary --
  // a terminal scan (failed/cancelled/interrupted) with no recorded end_time
  // has an unknown duration, not "however long ago it was created".
  if (!scan.end_time && scan.status !== 'in_progress' && scan.status !== 'queued') return '—';
  const start = new Date(scan.created_at.replace(/(\.\d{3})\d+/, '$1'));
  if (isNaN(start.getTime())) return '—';
  const end = scan.end_time ? new Date(scan.end_time.replace(/(\.\d{3})\d+/, '$1')) : new Date();
  const totalSeconds = Math.max(0, Math.floor((end.getTime() - start.getTime()) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

interface ScanUpdateProps {
  scan?: ScanDetails;
}

type ConfigComponent = {
  color: string,
  bgColor: string,
  borderColor: string,
  icon: React.ReactElement,
  progressColor: string
}

interface ConfigLayout {
  completed: ConfigComponent,
  failed: ConfigComponent,
  in_progress: ConfigComponent,
  interrupted: ConfigComponent,
  cancelled: ConfigComponent,
  default   : ConfigComponent
}

function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError && error.response?.data?.detail) {
    return error.response.data.detail;
  }
  return fallback;
}
 
function ScanUpdate({ scan }: ScanUpdateProps) {
  const [animatedProgress, setAnimatedProgress] = useState(0);
 
  const defaultScan: ScanDetails = {
    id: "6895a4aafd752429c18740bb",
    project_id: "68874418e816acffbf7c7729",
    scan_name: "HDBFS Security Scan",
    status: "in_progress",
    created_at: "2025-08-08T07:18:02.223",
    triggered_by: "68863cf8ee93d4964a00d585",
    total_files: 353,
    files_scanned: 142,
    findings: 7,
    end_time: null,
    metrics: {
      total_functions: 0,
      total_loc: 0,
      languages: []
    },
  };
 
  const phases = [
    { name: 'Initializing Scan', start: 0, end: 15 },
    { name: 'Scanning Files', start: 15, end: 20 },
    { name: 'Verifying Findings', start: 20, end: 95 },
    { name: 'Generating Report', start: 95, end: 100 }
  ];

  // Detection (Semgrep) runs as one atomic pass with no per-file progress, so
  // 0-20% just reflects "has the initial file/AST scan happened yet". The
  // bulk of scan time is the per-finding LLM verification loop, which DOES
  // report live progress (metrics.findings_progress, see lsast_scanner.py) --
  // that drives 20-95%. Deliberately does NOT use files_scanned/total_files
  // for this: those are real file counts, static after the initial AST pass,
  // and were previously (buggily) overloaded with a findings count to fake
  // this same live movement -- see the total_files/scanned mismatch fix.
  const calculatePercentage = (scan: ScanDetails): number => {
    if (scan.status === 'completed') return 100;
    if (scan.status === 'failed' || scan.status === 'cancelled') return 0;

    const fp = scan.metrics?.findings_progress;
    if (fp && fp.total > 0) {
      const verifyFraction = Math.min(fp.processed / fp.total, 1);
      return Math.min(20 + verifyFraction * 75, 99);
    }
    if (fp && fp.total === 0) return 95; // detection found nothing to verify
    return scan.total_files > 0 ? 15 : 0; // detection pass not done yet
  };
 
  const getCurrentPhase = (percentage: number, status: string): string => {
    if (status === 'completed') return 'Scan Complete';
    if (status === 'failed') return 'Scan Failed';
    if (status === 'cancelled') return 'Scan Cancelled';
    if (status === 'interrupted') return 'Scan Interrupted';
    if (status === 'pending') return 'Waiting to Start';
   
    const phase = phases.find(p => percentage >= p.start && percentage < p.end);
    return phase ? phase.name : 'Scanning Files';
  };
 
 
 
  const currentScan = scan || defaultScan;
  const percentage = calculatePercentage(currentScan);
  const currentPhase = getCurrentPhase(percentage, currentScan.status);

  const cancelScanMutation = useCancelScan();
  const resumeScanMutation = useResumeScan();

  const canCancel = currentScan.status === 'queued' || currentScan.status === 'in_progress';
  const canResume = currentScan.status === 'interrupted' || currentScan.status === 'cancelled';

  const handleCancel = () => {
    cancelScanMutation.mutate(currentScan.id, {
      onError: (error) => {
        toast('Cancel failed', { description: extractErrorMessage(error, 'Could not cancel the scan. Please try again.') });
      },
    });
  };

  const handleResume = () => {
    resumeScanMutation.mutate(currentScan.id, {
      onError: (error) => {
        toast('Resume failed', { description: extractErrorMessage(error, 'Could not resume the scan. Please try again.') });
      },
    });
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedProgress(percentage);
    }, 100);
    return () => clearTimeout(timer);
  }, [percentage]);
 
  const getStatusConfig = (status: any) => {
    const configs: ConfigLayout = {
      completed: {
        color: 'text-green-600',
        bgColor: 'bg-green-600/10',
        borderColor: 'border-green-600/20',
        icon: <CheckCircle className="w-5 h-5" />,
        progressColor: 'bg-green-600'
      },
      failed: {
        color: 'text-red-600',
        bgColor: 'bg-red-600/10',
        borderColor: 'border-red-600/20',
        icon: <AlertTriangle className="w-5 h-5" />,
        progressColor: 'bg-red-600'
      },
      in_progress: {
        color: 'text-blue-600',
        bgColor: 'bg-blue-600/10',
        borderColor: 'border-blue-600/20',
        icon: <Activity className="w-5 h-5 animate-pulse" />,
        progressColor: 'bg-blue-600'
      },
      interrupted: {
        color: 'text-amber-600',
        bgColor: 'bg-amber-600/10',
        borderColor: 'border-amber-600/20',
        icon: <PauseCircle className="w-5 h-5" />,
        progressColor: 'bg-amber-600'
      },
      cancelled: {
        color: 'text-[#404040] dark:text-[#a3a3a3]',
        bgColor: 'bg-[#404040]/10',
        borderColor: 'border-[#404040]/20',
        icon: <XCircle className="w-5 h-5" />,
        progressColor: 'bg-[#404040]'
      },
      default: {
        color: 'text-[#2d2d2d] dark:text-[#e5e5e5]',
        bgColor: 'bg-[#e5e5e5] dark:bg-[#2d2d2d]/50',
        borderColor: 'border-[#e5e5e5] dark:border-[#404040]',
        icon: <Clock className="w-5 h-5" />,
        progressColor: 'bg-[#2d2d2d]'
      }
    };
    return configs[status] || configs.default;
  };
 
  const statusConfig = getStatusConfig(currentScan.status);
  const circumference = 2 * Math.PI * 85;
  const strokeDashoffset = circumference - (animatedProgress / 100) * circumference;
 
  return (
    <div className=" p-6">
      <div className="max-w-8xl mx-auto space-y-6">
       
        {/* Header Card */}
        <div className=" rounded-2xl shadow-lg border border-[#e5e5e5] dark:border-[#404040] p-8">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className={`p-2 rounded-xl ${statusConfig.bgColor} ${statusConfig.color}`}>
                  <Shield className="w-6 h-6" />
                </div>
                <h1 className="text-3xl font-bold text-[#2d2d2d] dark:text-white">
                  {currentScan.scan_name}
                </h1>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 font-mono">
                ID: {currentScan.id}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className={`flex items-center gap-2 px-4 py-2 rounded-full ${statusConfig.bgColor} border ${statusConfig.borderColor}`}>
                <span className={statusConfig.color}>{statusConfig.icon}</span>
                <span className={`text-sm font-semibold capitalize ${statusConfig.color}`}>
                  {currentScan.status.replace('_', ' ')}
                </span>
              </div>

              {canCancel && (
                <ConfirmDialog
                  trigger={
                    <Button variant="outline" size="sm" disabled={cancelScanMutation.isPending}>
                      {cancelScanMutation.isPending ? 'Cancelling…' : 'Cancel Scan'}
                    </Button>
                  }
                  title="Cancel this scan?"
                  description="The scan will stop as soon as possible. You'll be able to resume it later without losing findings already found."
                  confirmLabel="Cancel Scan"
                  cancelLabel="Keep Scanning"
                  onConfirm={handleCancel}
                />
              )}

              {canResume && (
                <Button size="sm" disabled={resumeScanMutation.isPending} onClick={handleResume}>
                  {resumeScanMutation.isPending ? 'Resuming…' : 'Resume Scan'}
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Error Banner — only when there's actually something to explain */}
        {(currentScan.status === 'failed' || currentScan.status === 'interrupted') && currentScan.error && (
          <div className="rounded-2xl border border-red-200 dark:border-red-900/40 bg-red-50 dark:bg-red-950/20 p-5 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-semibold text-red-700 dark:text-red-400">
                {currentScan.status === 'failed' ? 'Scan failed' : 'Scan interrupted'}
              </div>
              <p className="text-sm text-red-600 dark:text-red-400/90 mt-1">{currentScan.error}</p>
            </div>
          </div>
        )}

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
         
          {/* Progress Circle Card */}
          <div className="lg:col-span-1">
            <div className=" rounded-2xl shadow-lg border border-[#e5e5e5] dark:border-[#404040] p-8 h-full">
              <h2 className="text-lg font-semibold text-[#2d2d2d] dark:text-white mb-6">
                Scan Progress
              </h2>
             
              <div className="flex flex-col items-center justify-center">
                {/* Circular Progress */}
                <div className="relative mb-6">
                  <svg className="w-52 h-52 transform -rotate-90" viewBox="0 0 200 200">
                    {/* Background Circle */}
                    <circle
                      cx="100"
                      cy="100"
                      r="85"
                      stroke="currentColor"
                      className="text-[#e5e5e5] dark:text-[#404040]"
                      strokeWidth="12"
                      fill="none"
                    />
                    {/* Progress Circle */}
                    <circle
                      cx="100"
                      cy="100"
                      r="85"
                      stroke="#bf0000"
                      strokeWidth="12"
                      fill="none"
                      strokeLinecap="round"
                      strokeDasharray={circumference}
                      strokeDashoffset={strokeDashoffset}
                      className="transition-all duration-1000 ease-out"
                    />
                  </svg>
                 
                  {/* Center Content */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                      <div className="text-5xl font-bold text-[#404040] dark:text-[#e5e5e5] mb-1">
                        {Math.round(animatedProgress)}%
                      </div>
                      <div className="text-sm text-gray-500 dark:text-gray-400 font-medium">
                        Completed
                      </div>
                    </div>
                  </div>
                </div>
 
                {/* Phase Info */}
                <div className="text-center w-full">
                  <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${statusConfig.bgColor} mb-3`}>
                    <div className={`w-2 h-2 rounded-full bg-[#bf0000] animate-pulse ${statusConfig.progressColor}`}></div>
                    <span className={`text-sm font-semibold ${statusConfig.color}`}>
                      {currentPhase}
                    </span>
                  </div>
                 
                  {currentScan.status === 'in_progress' && (
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {currentScan.files_scanned} / {currentScan.total_files} files
                    </p>
                  )}
                </div>
 
                {/* Progress Bar */}
                <div className="w-full mt-6">
                  <div className="h-2 bg-[#e5e5e5] dark:bg-[#404040] rounded-full overflow-hidden">
                    <div
                      className={`h-full ${statusConfig.progressColor} transition-all duration-1000 ease-out rounded-full`}
                      style={{ width: `${animatedProgress}%` }}
                    ></div>
                  </div>
                  {currentScan.status === 'in_progress' && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 text-center">
                      {currentScan.total_files - currentScan.files_scanned} files remaining
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
 
          {/* Stats Cards */}
          <div className="lg:col-span-2 space-y-6">
           
            {/* Scan Stats Grid */}
            <div className="rounded-2xl shadow-lg border border-[#e5e5e5] dark:border-[#404040] p-6 grid lg:grid-cols-3 gap-4">
              <div className="bg-[#bf0000]/20 rounded-xl shadow-lg p-5 transform transition-transform hover:scale-105">
                <div className="flex justify-between gap-3 mb-2">
                  <div className="text-sm opacity-90 font-medium">Findings</div>
                  <div className="p-2 bg-[#bf0000]/10 rounded-lg"><AlertTriangle className="w-8 h-8 text-[#bf0000]" /></div>
                </div>
                <div className="text-3xl font-bold mb-2">{currentScan.findings}</div>
                {currentScan.severity_counts && (
                  <div className="flex flex-wrap gap-2">
                    {SEVERITY_ORDER.filter(sev => (currentScan.severity_counts?.[sev] ?? 0) > 0).map(sev => (
                      <span key={sev} className="flex items-center gap-1">
                        <SecurityBadge severity={sev} size="sm" />
                        <span className="text-xs font-semibold">{currentScan.severity_counts?.[sev]}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-[#bf0000]/20 rounded-xl shadow-lg p-5 transform transition-transform hover:scale-105">
                <div className="flex justify-between gap-3 mb-2">
                  <div className="text-sm font-medium opacity-90">
                    {currentScan.status === 'in_progress' ? 'Running For' : 'Duration'}
                  </div>
                  <div className="p-2 bg-[#bf0000]/10 rounded-lg"><Clock className="w-8 h-8 text-[#bf0000]" /></div>
                </div>
                <div className="text-3xl font-bold mb-1">{formatDuration(currentScan)}</div>
              </div>

              <div className="bg-[#bf0000]/20 rounded-xl shadow-lg p-5 transform transition-transform hover:scale-105">
                <div className="flex justify-between gap-3 mb-2">
                  <div className="text-sm font-medium opacity-90">Started</div>
                  <div className="p-2 bg-[#bf0000]/10 rounded-lg"><Calendar className="w-8 h-8 text-[#bf0000]" /></div>
                </div>
                <div className="text-base font-semibold">{formatTimestamp(currentScan.created_at)}</div>
              </div>
            </div>
 
            {/* Code Analysis Stats — size/composition only, not a risk signal, so it's
                deliberately lower-emphasis than the Findings/Duration/Started stats above. */}
            <div className="bg-white dark:bg-[#2d2d2d] rounded-2xl border border-[#e5e5e5] dark:border-[#404040] p-6">
              <h2 className="text-base font-medium text-[#404040] dark:text-[#a3a3a3] mb-1 flex items-center gap-2">
                <Code className="w-4 h-4" />
                Code Analysis Overview
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                Size and composition of the scanned code — not a security signal.
              </p>

              <div className="grid lg:grid-cols-2 xl:grid-cols-3 gap-4">
                <div className="p-4 bg-[#e5e5e5] dark:bg-[#1a1a1a] rounded-xl border border-[#e5e5e5] dark:border-[#404040]">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="p-2 bg-[#bf0000]/10 rounded-lg">
                      <Layers className="w-5 h-5 text-[#bf0000]" />
                    </div>
                    <div className="text-2xl font-bold text-[#2d2d2d] dark:text-white">
                      {currentScan.metrics.total_loc}
                    </div>
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400 font-medium">Lines of Code</div>
                </div>
               
                <div className="p-4 bg-[#e5e5e5] dark:bg-[#1a1a1a] rounded-xl border border-[#e5e5e5] dark:border-[#404040]">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="p-2 bg-[#bf0000]/10 rounded-lg">
                      <Code className="w-5 h-5 text-[#bf0000]" />
                    </div>
                    <div className="text-2xl font-bold text-[#2d2d2d] dark:text-white">
                      {currentScan.metrics.total_functions}
                    </div>
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400 font-medium">Total Functions</div>
                </div>
               
                <div className="p-4 bg-[#e5e5e5] dark:bg-[#1a1a1a] rounded-xl border border-[#e5e5e5] dark:border-[#404040]">
                  <div className="text-sm text-gray-600 dark:text-gray-400 font-medium mb-2">Languages</div>
                    <div className='flex flex-wrap gap-2'>
                      {
                        currentScan.metrics.languages.map((lang) => (
                          <span key={lang} className='bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded-2xl capitalize'>
                            {lang}
                          </span>
                        ))
                      }
                    </div>
                     
                </div>
 
              </div>
            </div>
 
          </div>
        </div>
      </div>
    </div>
  );
}
 
export default ScanUpdate;