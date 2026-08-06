import { useState } from 'react';
import type { FormEvent } from 'react';

type Props = {
  error: string | null;
  submitting: boolean;
  onSubmit: (password: string) => void;
};

export function ActivationGate({ error, submitting, onSubmit }: Props) {
  const [password, setPassword] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (password.trim()) onSubmit(password);
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: '#2D2D2D' }}>
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl bg-white text-black shadow-2xl overflow-hidden px-8 py-8 text-center space-y-4"
      >
        <h1 className="text-2xl font-bold">Activate Code Sense</h1>
        <p className="text-sm text-gray-600">
          Enter the activation password to set up this installation. This is a one-time step —
          the app won't ask again on this machine.
        </p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Activation password"
          className="w-full px-4 py-3 rounded-lg border border-gray-300 text-black focus:outline-none focus:ring-2"
          style={{ ['--tw-ring-color' as string]: '#BF0000' }}
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting || !password.trim()}
          className="w-full py-3 rounded-lg text-white disabled:opacity-50"
          style={{ backgroundColor: '#BF0000' }}
        >
          {submitting ? 'Activating…' : 'Activate'}
        </button>
      </form>
    </div>
  );
}
