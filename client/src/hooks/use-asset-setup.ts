import { useCallback, useEffect, useState } from 'react';
import { listen } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/core';

export type AssetSetupState =
  | { status: 'pending'; progress: Record<string, { bytes: number; total: number }> }
  | { status: 'ready' }
  | { status: 'failed'; asset: string; reason: string };

type ProgressPayload = { asset: string; bytes: number; total: number };
type FailedPayload = { asset: string; reason: string };

export function useAssetSetup(): AssetSetupState & { retry: () => void } {
  const [state, setState] = useState<AssetSetupState>({ status: 'pending', progress: {} });

  useEffect(() => {
    let cancelled = false;
    const unlisten: Array<() => void> = [];

    listen<ProgressPayload>('asset-setup-progress', (event) => {
      setState((prev) =>
        prev.status === 'pending'
          ? {
              status: 'pending',
              progress: {
                ...prev.progress,
                [event.payload.asset]: { bytes: event.payload.bytes, total: event.payload.total },
              },
            }
          : prev,
      );
    }).then((fn) => {
      if (cancelled) fn();
      else unlisten.push(fn);
    });

    listen('asset-setup-complete', () => {
      setState({ status: 'ready' });
    }).then((fn) => {
      if (cancelled) fn();
      else unlisten.push(fn);
    });

    listen<FailedPayload>('asset-setup-failed', (event) => {
      setState({ status: 'failed', asset: event.payload.asset, reason: event.payload.reason });
    }).then((fn) => {
      if (cancelled) fn();
      else unlisten.push(fn);
    });

    return () => {
      cancelled = true;
      unlisten.forEach((fn) => fn());
    };
  }, []);

  const retry = useCallback(() => {
    setState({ status: 'pending', progress: {} });
    void invoke('retry_asset_setup');
  }, []);

  return { ...state, retry };
}
