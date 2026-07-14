import type { AssetSetupState } from '@/hooks/use-asset-setup';

const ASSET_LABELS: Record<string, string> = {
  model: 'AI model',
  'grype-db': 'vulnerability database',
};

type Props = {
  state: AssetSetupState & { retry: () => void };
};

export function FirstRunSetup({ state }: Props) {
  if (state.status === 'ready') {
    return null;
  }

  if (state.status === 'failed') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: '#2D2D2D' }}>
        <div className="w-full max-w-md rounded-2xl bg-white text-black shadow-2xl overflow-hidden px-8 py-8 text-center space-y-4">
          <h1 className="text-2xl font-bold">Setup failed</h1>
          <p className="text-sm text-gray-600">
            Couldn't prepare the {ASSET_LABELS[state.asset] ?? state.asset}: {state.reason}
          </p>
          <button
            type="button"
            className="w-full py-3 rounded-lg text-white"
            style={{ backgroundColor: '#BF0000' }}
            onClick={state.retry}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const entries = Object.entries(state.progress);
  const totalBytes = entries.reduce((sum, [, p]) => sum + p.total, 0);
  const writtenBytes = entries.reduce((sum, [, p]) => sum + p.bytes, 0);
  const percent = totalBytes > 0 ? Math.round((writtenBytes / totalBytes) * 100) : 0;

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: '#2D2D2D' }}>
      <div className="w-full max-w-md rounded-2xl bg-white text-black shadow-2xl overflow-hidden px-8 py-8 text-center space-y-4">
        <h1 className="text-2xl font-bold">Setting up Code Sense</h1>
        <p className="text-sm text-gray-600">
          Preparing the AI model and vulnerability database (first launch only)…
        </p>
        <div
          className="w-full h-2 rounded-full bg-gray-200 overflow-hidden"
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Setup progress"
        >
          <div className="h-full rounded-full" style={{ width: `${percent}%`, backgroundColor: '#BF0000' }} />
        </div>
        <p className="text-xs text-gray-500">{percent}%</p>
      </div>
    </div>
  );
}
