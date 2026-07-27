import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, test, expect, vi } from 'vitest';
import LicenseStatusCard from './license-status-card';
import { licenseService } from '@/services/license.service';

vi.mock('@/services/license.service', () => ({
  licenseService: { getStatus: vi.fn() },
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('LicenseStatusCard', () => {
  test('renders active state with days remaining and expiry date', async () => {
    vi.mocked(licenseService.getStatus).mockResolvedValue({
      state: 'active',
      first_seen: '2026-06-20T00:00:00Z',
      expires_at: '2026-07-20T00:00:00Z',
      days_remaining: 12,
    });
    renderWithClient(<LicenseStatusCard />);

    expect(await screen.findByText(/License Active/i)).toBeInTheDocument();
    expect(await screen.findByText(/12 days remaining/i)).toBeInTheDocument();
  });

  test('renders tampered state with the read-only explanation', async () => {
    vi.mocked(licenseService.getStatus).mockResolvedValue({
      state: 'tampered',
      first_seen: null,
      expires_at: null,
      days_remaining: 0,
    });
    renderWithClient(<LicenseStatusCard />);

    expect(await screen.findByText(/License Invalid/i)).toBeInTheDocument();
    expect(await screen.findByText(/Validation failed/i)).toBeInTheDocument();
  });

  test('renders nothing while the query is loading', () => {
    vi.mocked(licenseService.getStatus).mockReturnValue(new Promise(() => {}));
    const { container } = renderWithClient(<LicenseStatusCard />);
    expect(container).toBeEmptyDOMElement();
  });
});
