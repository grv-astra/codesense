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
  invoke: vi.fn(),
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
});
