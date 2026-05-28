import { useLicenseStatus } from '@/hooks/use-license';
import { AlertTriangle, Lock } from 'lucide-react';

export default function LicenseBanner() {
  const { data } = useLicenseStatus();
  if (!data || data.state === 'active') return null;

  if (data.state === 'expiring') {
    const d = data.days_remaining;
    return (
      <div className="flex items-center gap-2 rounded-md border border-amber-300 bg-amber-100 px-4 py-2 text-sm text-amber-900">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span>
          Your license expires in {d} day{d === 1 ? '' : 's'}. Renew to avoid read-only mode.
        </span>
      </div>
    );
  }

  // expired | tampered
  return (
    <div className="flex items-center gap-2 rounded-md border border-red-300 bg-red-100 px-4 py-2 text-sm text-red-900">
      <Lock className="h-4 w-4 shrink-0" />
      <span>
        {data.state === 'tampered'
          ? 'License validation failed — the app is in read-only mode. Creating scans and edits are disabled.'
          : 'Your license has expired — the app is in read-only mode. Existing data stays viewable, but new scans and edits are disabled.'}
      </span>
    </div>
  );
}
