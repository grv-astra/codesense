import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import { ActivationGate } from './ActivationGate';

describe('ActivationGate', () => {
  test('submit button is disabled until a password is typed', () => {
    render(<ActivationGate error={null} submitting={false} onSubmit={vi.fn()} />);
    expect(screen.getByRole('button', { name: /activate/i })).toBeDisabled();
  });

  test('submits the typed password', () => {
    const onSubmit = vi.fn();
    render(<ActivationGate error={null} submitting={false} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByPlaceholderText(/activation password/i), {
      target: { value: 'the-password' },
    });
    fireEvent.click(screen.getByRole('button', { name: /activate/i }));
    expect(onSubmit).toHaveBeenCalledWith('the-password');
  });

  test('shows the error message when activation fails', () => {
    render(<ActivationGate error="Incorrect activation password." submitting={false} onSubmit={vi.fn()} />);
    expect(screen.getByText(/incorrect activation password/i)).toBeInTheDocument();
  });

  test('shows a submitting state and disables the button while in flight', () => {
    render(<ActivationGate error={null} submitting={true} onSubmit={vi.fn()} />);
    expect(screen.getByRole('button', { name: /activating/i })).toBeDisabled();
  });
});
