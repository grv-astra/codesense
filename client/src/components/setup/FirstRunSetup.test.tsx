import { render, screen } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import { FirstRunSetup } from './FirstRunSetup';

describe('FirstRunSetup', () => {
  test('shows progress percentage while pending', () => {
    render(
      <FirstRunSetup
        state={{
          status: 'pending',
          progress: { model: { bytes: 50, total: 100 } },
          retry: vi.fn(),
        }}
      />,
    );
    expect(screen.getByText(/50%/)).toBeInTheDocument();
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
