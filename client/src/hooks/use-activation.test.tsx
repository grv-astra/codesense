import { renderHook, act } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';

const getStatus = vi.fn();
const activate = vi.fn();

vi.mock('@/services/activation.service', () => ({
  activationService: {
    getStatus: (...args: unknown[]) => getStatus(...args),
    activate: (...args: unknown[]) => activate(...args),
  },
}));

const isTauri = vi.fn(() => true);
vi.mock('@tauri-apps/api/core', () => ({
  isTauri: () => isTauri(),
}));

import { useActivation } from './use-activation';

// waitFor's internal polling doesn't play well with fake timers here, so
// tests advance fake timers explicitly, wrapped in act() so the resulting
// state updates are flushed into `result.current` before assertions run.
const flush = (ms = 0) => act(async () => {
  await vi.advanceTimersByTimeAsync(ms);
});

describe('useActivation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    isTauri.mockReturnValue(true);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('does not check until ready=true', async () => {
    const { result, rerender } = renderHook(({ ready }) => useActivation(ready), {
      initialProps: { ready: false },
    });
    await flush();
    expect(getStatus).not.toHaveBeenCalled();
    expect(result.current.state.status).toBe('checking');

    getStatus.mockResolvedValue({ configured: true, activated: true });
    rerender({ ready: true });
    await flush();
    expect(getStatus).toHaveBeenCalledTimes(1);
    expect(result.current.state.status).toBe('unlocked');
  });

  test('retries on failure instead of immediately locking (avoids the backend-not-up-yet false negative)', async () => {
    getStatus
      .mockRejectedValueOnce(new Error('connection refused'))
      .mockRejectedValueOnce(new Error('connection refused'))
      .mockResolvedValueOnce({ configured: true, activated: true });

    const { result } = renderHook(() => useActivation(true));

    await flush();
    expect(result.current.state.status).toBe('checking'); // first failure: still checking, not locked

    await flush(1000);
    await flush(1000);
    expect(result.current.state.status).toBe('unlocked');
    expect(getStatus).toHaveBeenCalledTimes(3);
  });

  test('locks only after retries are genuinely exhausted', async () => {
    getStatus.mockRejectedValue(new Error('connection refused'));
    const { result } = renderHook(() => useActivation(true));

    await flush();
    expect(result.current.state.status).toBe('checking');

    // 20 retries * 1000ms -- run them all out.
    await flush(21 * 1000);
    expect(result.current.state.status).toBe('locked');
  });

  test('unlocked immediately when the first check succeeds and is activated', async () => {
    getStatus.mockResolvedValue({ configured: true, activated: true });
    const { result } = renderHook(() => useActivation(true));
    await flush();
    expect(result.current.state.status).toBe('unlocked');
    expect(getStatus).toHaveBeenCalledTimes(1);
  });

  test('locked when configured and not yet activated (a real, definitive answer)', async () => {
    getStatus.mockResolvedValue({ configured: true, activated: false });
    const { result } = renderHook(() => useActivation(true));
    await flush();
    expect(result.current.state.status).toBe('locked');
  });

  test('not_required on the web build (not Tauri)', async () => {
    isTauri.mockReturnValue(false);
    const { result } = renderHook(() => useActivation(true));
    await flush();
    expect(result.current.state.status).toBe('not_required');
    expect(getStatus).not.toHaveBeenCalled();
  });
});
