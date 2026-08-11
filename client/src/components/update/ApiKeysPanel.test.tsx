import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { ApiKeysPanel } from './ApiKeysPanel';

vi.mock('@/services/apikey.service', () => ({
  apiKeyService: {
    listApiKeys: vi.fn(),
    createApiKey: vi.fn(),
    revokeApiKey: vi.fn(),
  },
}));

import { apiKeyService } from '@/services/apikey.service';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('ApiKeysPanel', () => {
  beforeEach(() => {
    vi.mocked(apiKeyService.listApiKeys).mockReset();
    vi.mocked(apiKeyService.createApiKey).mockReset();
    vi.mocked(apiKeyService.revokeApiKey).mockReset();
  });

  test('shows empty state when there are no keys', async () => {
    vi.mocked(apiKeyService.listApiKeys).mockResolvedValue([]);
    renderWithClient(<ApiKeysPanel projectId="proj1" />);
    expect(await screen.findByText(/no api keys yet/i)).toBeInTheDocument();
  });

  test('lists existing keys', async () => {
    vi.mocked(apiKeyService.listApiKeys).mockResolvedValue([
      {
        id: 'k1',
        name: 'azure-devops-prod',
        key_prefix: 'csk_ab12',
        created_at: '2026-08-11T00:00:00Z',
        last_used_at: null,
        revoked_at: null,
      },
    ]);
    renderWithClient(<ApiKeysPanel projectId="proj1" />);
    expect(await screen.findByText('azure-devops-prod')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  test('generating a key shows the plaintext once', async () => {
    vi.mocked(apiKeyService.listApiKeys).mockResolvedValue([]);
    vi.mocked(apiKeyService.createApiKey).mockResolvedValue({
      id: 'k2',
      name: 'new-key',
      key_prefix: 'csk_zz99',
      created_at: '2026-08-11T00:00:00Z',
      last_used_at: null,
      revoked_at: null,
      key: 'csk_zz99fullsecretvalue',
    });
    renderWithClient(<ApiKeysPanel projectId="proj1" />);

    fireEvent.click(await screen.findByRole('button', { name: /generate new key/i }));
    fireEvent.change(screen.getByLabelText(/key name/i), { target: { value: 'new-key' } });
    fireEvent.click(screen.getByRole('button', { name: /^generate$/i }));

    expect(await screen.findByText('csk_zz99fullsecretvalue')).toBeInTheDocument();
    expect(apiKeyService.createApiKey).toHaveBeenCalledWith('proj1', { name: 'new-key' });
  });

  test('revoking a key calls the service', async () => {
    vi.mocked(apiKeyService.listApiKeys).mockResolvedValue([
      {
        id: 'k1',
        name: 'azure-devops-prod',
        key_prefix: 'csk_ab12',
        created_at: '2026-08-11T00:00:00Z',
        last_used_at: null,
        revoked_at: null,
      },
    ]);
    vi.mocked(apiKeyService.revokeApiKey).mockResolvedValue({
      id: 'k1',
      name: 'azure-devops-prod',
      key_prefix: 'csk_ab12',
      created_at: '2026-08-11T00:00:00Z',
      last_used_at: null,
      revoked_at: '2026-08-11T01:00:00Z',
    });
    renderWithClient(<ApiKeysPanel projectId="proj1" />);

    fireEvent.click(await screen.findByRole('button', { name: /revoke/i }));
    await waitFor(() => expect(apiKeyService.revokeApiKey).toHaveBeenCalledWith('proj1', 'k1'));
  });
});
