export type LicenseState = 'active' | 'expiring' | 'expired' | 'tampered';

export interface LicenseStatus {
  state: LicenseState;
  first_seen: string | null;
  expires_at: string | null;
  days_remaining: number;
}
