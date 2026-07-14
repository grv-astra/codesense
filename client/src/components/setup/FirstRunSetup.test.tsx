import { render, screen } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import { FirstRunSetup } from './FirstRunSetup';

describe('FirstRunSetup', () => {
  test('shows progress percentage while pending', () => {
    render(
      <FirstRunSetup
        state={{
          status: 'pending',
          // model is weighted at 50% of the overall bar and is itself 50%
          // done, so the fixed 50/50 weighting yields 25% overall.
          progress: { model: { bytes: 50, total: 100 } },
          retry: vi.fn(),
        }}
      />,
    );
    expect(screen.getByText(/25%/)).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '25');
  });

  test('percent is monotonically non-decreasing when grype-db tracking begins after model completes', () => {
    const { rerender } = render(
      <FirstRunSetup
        state={{
          status: 'pending',
          progress: { model: { bytes: 100, total: 100 } },
          retry: vi.fn(),
        }}
      />,
    );
    expect(screen.getByText(/50%/)).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50');

    rerender(
      <FirstRunSetup
        state={{
          status: 'pending',
          progress: {
            model: { bytes: 100, total: 100 },
            'grype-db': { bytes: 1, total: 1000 },
          },
          retry: vi.fn(),
        }}
      />,
    );
    const percentAfter = Number(screen.getByRole('progressbar').getAttribute('aria-valuenow'));
    expect(percentAfter).toBeGreaterThanOrEqual(50);
  });

  test('shows the failure reason and calls retry on click', () => {
    const retry = vi.fn();
    render(
      <FirstRunSetup state={{ status: 'failed', asset: 'grype-db', reason: 'disk full', retry }} />,
    );
    expect(screen.getByText(/disk full/)).toBeInTheDocument();
    screen.getByRole('button', { name: /retry/i }).click();
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
