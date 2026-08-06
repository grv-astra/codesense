import { useCallback, useEffect, useState } from 'react';
import { isTauri } from '@tauri-apps/api/core';
import { activationService } from '@/services/activation.service';

export type ActivationState =
  | { status: 'checking' }
  | { status: 'not_required' }
  | { status: 'locked' }
  | { status: 'unlocked' };

export function useActivation() {
  const [state, setState] = useState<ActivationState>({ status: 'checking' });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const check = useCallback(() => {
    // The web build (this repo's primary target) has no baked activation
    // password at all -- only a packaged desktop build can opt into the
    // gate (see main.rs::ACTIVATION_PASSWORD_HASH) -- so skip the check
    // entirely there rather than depending on a backend that may not even
    // be reachable yet.
    if (!isTauri()) {
      setState({ status: 'not_required' });
      return;
    }
    activationService.getStatus()
      .then(({ configured, activated }) => {
        setState({ status: !configured || activated ? 'unlocked' : 'locked' });
      })
      .catch(() => setState({ status: 'locked' }));
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  const submit = useCallback((password: string) => {
    setSubmitting(true);
    setError(null);
    activationService.activate(password)
      .then(({ activated }) => {
        if (activated) {
          setState({ status: 'unlocked' });
        } else {
          setError('Incorrect activation password.');
        }
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Incorrect activation password.');
      })
      .finally(() => setSubmitting(false));
  }, []);

  return { state, error, submitting, submit };
}
