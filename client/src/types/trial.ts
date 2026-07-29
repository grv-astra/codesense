export interface TrialStatus {
  trial_mode: boolean;
  limit: number | null;
  used: number;
  remaining: number | null;
}
