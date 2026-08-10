import { useCallback, useEffect, useState } from 'react';
import { isTauri } from '@tauri-apps/api/core';
import { activationService } from '@/services/activation.service';

export type ActivationState =
  | { status: 'checking' }
  | { status: 'not_required' }
  | { status: 'locked' }
  | { status: 'unlocked' };

const MAX_RETRIES = 20;
const RETRY_DELAY_MS = 1000;

/**
 * @param ready Only start checking once true. main.rs spawns the backend
 * AFTER asset setup finishes, so checking before that is guaranteed to hit
 * a not-yet-listening backend -- pass e.g. `assetSetup.status === 'ready'`.
 */
export function useActivation(ready: boolean) {
  const [state, setState] = useState<ActivationState>({ status: 'checking' });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const check = useCallback(() => {
    // The web build (this repo's primary target) has no baked activation
    // password at all -- only a packaged desktop build can opt into the
    // gate (see main.rs::ACTIVATION_PASSWORD_HASH).
    if (!isTauri()) {
      setState({ status: 'not_required' });
      return () => {};
    }

    let cancelled = false;
    const attempt = (retriesLeft: number) => {
      activationService.getStatus()
        .then(({ configured, activated }) => {
          if (cancelled) return;
          setState({ status: !configured || activated ? 'unlocked' : 'locked' });
        })
        .catch(() => {
          if (cancelled) return;
          // A failed request here is almost always the backend not having
          // finished starting yet, not a genuine "not activated" -- retry
          // instead of showing the activation gate on a false negative
          // (this was flashing on every normal launch). Only fall back to
          // "locked" after real, repeated attempts.
          if (retriesLeft > 0) {
            setTimeout(() => attempt(retriesLeft - 1), RETRY_DELAY_MS);
          } else {
            setState({ status: 'locked' });
          }
        });
    };
    attempt(MAX_RETRIES);

    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!ready) return;
    return check();
  }, [ready, check]);

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
