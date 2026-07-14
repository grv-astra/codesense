import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';

const listeners: Record<string, (event: { payload: unknown }) => void> = {};

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn((eventName: string, callback: (event: { payload: unknown }) => void) => {
    listeners[eventName] = callback;
    return Promise.resolve(() => {
      delete listeners[eventName];
    });
  }),
}));

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn((command: string) => {
    if (command === 'get_asset_setup_status') {
      return Promise.resolve({ status: 'pending' });
    }
    return Promise.resolve();
  }),
}));

import { useAssetSetup } from './use-asset-setup';
import { invoke } from '@tauri-apps/api/core';

describe('useAssetSetup', () => {
  beforeEach(() => {
    for (const key of Object.keys(listeners)) delete listeners[key];
    vi.clearAllMocks();
  });

  test('starts pending and transitions to ready on asset-setup-complete', async () => {
    const { result } = renderHook(() => useAssetSetup());
    expect(result.current.status).toBe('pending');

    await waitFor(() => expect(listeners['asset-setup-complete']).toBeDefined());
    act(() => {
      listeners['asset-setup-complete']({ payload: undefined });
    });

    expect(result.current.status).toBe('ready');
  });

  test('tracks per-asset progress while pending', async () => {
    const { result } = renderHook(() => useAssetSetup());
    await waitFor(() => expect(listeners['asset-setup-progress']).toBeDefined());

    act(() => {
      listeners['asset-setup-progress']({ payload: { asset: 'model', bytes: 500, total: 1000 } });
    });

    expect(result.current.status).toBe('pending');
    if (result.current.status === 'pending') {
      expect(result.current.progress.model).toEqual({ bytes: 500, total: 1000 });
    }
  });

  test('transitions to failed with reason and retry() calls retry_asset_setup', async () => {
    const { result } = renderHook(() => useAssetSetup());
    await waitFor(() => expect(listeners['asset-setup-failed']).toBeDefined());

    act(() => {
      listeners['asset-setup-failed']({ payload: { asset: 'grype-db', reason: 'disk full' } });
    });

    expect(result.current.status).toBe('failed');
    if (result.current.status === 'failed') {
      expect(result.current.reason).toBe('disk full');
    }

    act(() => {
      result.current.retry();
    });
    expect(invoke).toHaveBeenCalledWith('retry_asset_setup');
  });

  test('ignores a stale asset-setup-progress event once state is already failed', async () => {
    const { result } = renderHook(() => useAssetSetup());
    await waitFor(() => expect(listeners['asset-setup-failed']).toBeDefined());

    act(() => {
      listeners['asset-setup-failed']({ payload: { asset: 'grype-db', reason: 'disk full' } });
    });
    expect(result.current.status).toBe('failed');

    act(() => {
      listeners['asset-setup-progress']({ payload: { asset: 'model', bytes: 10, total: 100 } });
    });

    expect(result.current.status).toBe('failed');
    if (result.current.status === 'failed') {
      expect(result.current.reason).toBe('disk full');
    }
  });

  test('ignores a stale asset-setup-complete event arriving after asset-setup-failed', async () => {
    const { result } = renderHook(() => useAssetSetup());
    await waitFor(() => {
      expect(listeners['asset-setup-failed']).toBeDefined();
      expect(listeners['asset-setup-complete']).toBeDefined();
    });

    act(() => {
      listeners['asset-setup-failed']({ payload: { asset: 'grype-db', reason: 'disk full' } });
    });
    expect(result.current.status).toBe('failed');

    // A straggling "complete" event arrives out of order after "failed" already fired.
    act(() => {
      listeners['asset-setup-complete']({ payload: undefined });
    });

    expect(result.current.status).toBe('failed');
    if (result.current.status === 'failed') {
      expect(result.current.reason).toBe('disk full');
    }
  });

  test('picks up an already-ready status via get_asset_setup_status if the complete event was missed', async () => {
    (invoke as ReturnType<typeof vi.fn>).mockImplementation((command: string) => {
      if (command === 'get_asset_setup_status') {
        return Promise.resolve({ status: 'ready' });
      }
      return Promise.resolve();
    });

    const { result } = renderHook(() => useAssetSetup());

    await waitFor(() => expect(result.current.status).toBe('ready'));
  });

  test('picks up an already-failed status via get_asset_setup_status if the failed event was missed', async () => {
    (invoke as ReturnType<typeof vi.fn>).mockImplementation((command: string) => {
      if (command === 'get_asset_setup_status') {
        return Promise.resolve({ status: 'failed', asset: 'model', reason: 'reinstall required: manifest.json is missing' });
      }
      return Promise.resolve();
    });

    const { result } = renderHook(() => useAssetSetup());

    await waitFor(() => expect(result.current.status).toBe('failed'));
    if (result.current.status === 'failed') {
      expect(result.current.asset).toBe('model');
      expect(result.current.reason).toBe('reinstall required: manifest.json is missing');
    }
  });

  test('retry() transitions to failed when invoke() rejects', async () => {
    // mockRejectedValueOnce would queue by call order, not by command name —
    // since mount now also calls invoke('get_asset_setup_status') first, a
    // plain "once" rejection would hit that call instead of retry()'s later
    // invoke('retry_asset_setup'). Route by command name instead.
    (invoke as ReturnType<typeof vi.fn>).mockImplementation((command: string) => {
      if (command === 'get_asset_setup_status') {
        return Promise.resolve({ status: 'pending' });
      }
      if (command === 'retry_asset_setup') {
        return Promise.reject(new Error('backend unreachable'));
      }
      return Promise.resolve();
    });
    const { result } = renderHook(() => useAssetSetup());

    act(() => {
      result.current.retry();
    });
    expect(result.current.status).toBe('pending');

    await waitFor(() => expect(result.current.status).toBe('failed'));
    if (result.current.status === 'failed') {
      expect(result.current.asset).toBe('unknown');
      expect(result.current.reason).toBe('backend unreachable');
    }
  });
});
