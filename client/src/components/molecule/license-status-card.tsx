import { Card } from '@/components/atomic/card';
import { useLicenseStatus } from '@/hooks/use-license';
import type { LicenseState } from '@/types/license';
import { AlertTriangle, Lock, ShieldCheck } from 'lucide-react';

const STATE_CONFIG: Record<LicenseState, {
  label: string;
  icon: typeof ShieldCheck;
  color: string;
  iconBg: string;
}> = {
  active: {
    label: 'License Active',
    icon: ShieldCheck,
    color: 'text-emerald-600 dark:text-emerald-400',
    iconBg: 'bg-emerald-600',
  },
  expiring: {
    label: 'License Expiring Soon',
    icon: AlertTriangle,
    color: 'text-amber-600 dark:text-amber-400',
    iconBg: 'bg-amber-600',
  },
  expired: {
    label: 'License Expired',
    icon: Lock,
    color: 'text-red-600 dark:text-red-400',
    iconBg: 'bg-red-700',
  },
  tampered: {
    label: 'License Invalid',
    icon: Lock,
    color: 'text-red-600 dark:text-red-400',
    iconBg: 'bg-red-700',
  },
};

const describeDetail = (state: LicenseState, daysRemaining: number, expiresAt: string | null) => {
  if (state === 'active' || state === 'expiring') {
    if (expiresAt) {
      const date = new Date(expiresAt).toLocaleDateString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
      });
      return `${daysRemaining} day${daysRemaining === 1 ? '' : 's'} remaining · expires ${date}`;
    }
    return `${daysRemaining} day${daysRemaining === 1 ? '' : 's'} remaining`;
  }
  if (state === 'tampered') return 'Validation failed — app is in read-only mode';
  return 'Expired — app is in read-only mode';
};

const LicenseStatusCard = () => {
  const { data, isLoading } = useLicenseStatus();

  if (isLoading || !data) return null;

  const config = STATE_CONFIG[data.state];
  const Icon = config.icon;

  return (
    <Card className="px-4 py-3 rounded-md border-0 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-md ${config.iconBg} shrink-0`}>
          <Icon size={20} className="text-white" />
        </div>
        <div className="flex flex-col">
          <span className={`text-sm font-semibold ${config.color}`}>{config.label}</span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {describeDetail(data.state, data.days_remaining, data.expires_at)}
          </span>
        </div>
      </div>
    </Card>
  );
};

export default LicenseStatusCard;
