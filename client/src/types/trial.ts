export interface TrialTypeStatus {
  limit: number | null;
  used: number;
  remaining: number | null;
}

export interface TrialStatus {
  trial_mode: boolean;
  code: TrialTypeStatus;
  sbom: TrialTypeStatus;
}
