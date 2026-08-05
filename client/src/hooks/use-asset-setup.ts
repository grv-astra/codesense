import { useCallback, useEffect, useState } from 'react';
import { listen } from '@tauri-apps/api/event';
import { invoke, isTauri } from '@tauri-apps/api/core';

export type AssetSetupState =
  | { status: 'pending'; progress: Record<string, { bytes: number; total: number }> }
  | { status: 'ready' }
  | { status: 'failed'; asset: string; reason: string };

type ProgressPayload = { asset: string; bytes: number; total: number };
type FailedPayload = { asset: string; reason: string };
type StatusPayload =
  | { status: 'pending' }
  | { status: 'ready' }
  | { status: 'failed'; asset: string; reason: string };

export function useAssetSetup(): AssetSetupState & { retry: () => void } {
  const [state, setState] = useState<AssetSetupState>({ status: 'pending', progress: {} });

  useEffect(() => {
    // The desktop build downloads/reassembles the model + vuln DB on first
    // launch and reports progress over Tauri IPC; the web build (this repo's
    // primary target) has no such step -- those assets are already available
    // server-side -- so there is nothing to wait for outside Tauri.
    if (!isTauri()) {
      setState({ status: 'ready' });
      return;
    }

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
      setState((prev) => (prev.status === 'ready' || prev.status === 'failed' ? prev : { status: 'ready' }));
    }).then((fn) => {
      if (cancelled) fn();
      else unlisten.push(fn);
    });

    listen<FailedPayload>('asset-setup-failed', (event) => {
      setState((prev) =>
        prev.status === 'ready' || prev.status === 'failed'
          ? prev
          : { status: 'failed', asset: event.payload.asset, reason: event.payload.reason },
      );
    }).then((fn) => {
      if (cancelled) fn();
      else unlisten.push(fn);
    });

    // Once `.done` markers exist, reassembly on the Rust side can finish (and
    // emit `asset-setup-complete`/`-failed`) in well under a second — often
    // faster than this webview finishes loading its JS and registering the
    // listeners above, so an event-only signal can fire before anyone is
    // listening and be lost forever. This one-shot status check right after
    // registration closes that race: it picks up whatever already happened,
    // while the listeners above remain the source of truth for the slower
    // first-run case where reassembly is still in progress at mount time.
    invoke<StatusPayload>('get_asset_setup_status').then((result) => {
      if (cancelled) return;
      if (result.status === 'ready') {
        setState((prev) => (prev.status === 'ready' || prev.status === 'failed' ? prev : { status: 'ready' }));
      } else if (result.status === 'failed') {
        setState((prev) =>
          prev.status === 'ready' || prev.status === 'failed'
            ? prev
            : { status: 'failed', asset: result.asset, reason: result.reason },
        );
      }
    });

    return () => {
      cancelled = true;
      unlisten.forEach((fn) => fn());
    };
  }, []);

  const retry = useCallback(() => {
    setState({ status: 'pending', progress: {} });
    invoke('retry_asset_setup').catch((error: unknown) => {
      const reason = error instanceof Error ? error.message : String(error);
      setState({ status: 'failed', asset: 'unknown', reason });
    });
  }, []);

  return { ...state, retry };
}
