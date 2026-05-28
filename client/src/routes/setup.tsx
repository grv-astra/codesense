import { Button } from '@/components/atomic/button';
import { Input } from '@/components/atomic/input';
import { useCreateInitialAdmin, useSetupStatus } from '@/hooks/use-setup';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { AxiosError } from 'axios';
import { Lock, Mail, User } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

export const Route = createFileRoute('/setup')({
  component: SetupPage,
});

function SetupPage() {
  const navigate = useNavigate();
  const { data: status, isLoading } = useSetupStatus();
  const createAdmin = useCreateInitialAdmin();
  const [form, setForm] = useState({ name: '', email: '', company: '', password: '' });

  // If setup is already done, this page is not needed.
  useEffect(() => {
    if (status && !status.setup_needed) {
      navigate({ to: '/login' });
    }
  }, [status, navigate]);

  const onChange = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    createAdmin.mutate(
      { name: form.name, email: form.email, password: form.password, company: form.company || undefined },
      {
        onSuccess: () => {
          toast('Administrator created', { description: 'You can now sign in.' });
          navigate({ to: '/login' });
        },
        onError: (err) => {
          const detail =
            err instanceof AxiosError ? (err.response?.data?.detail as string | undefined) : undefined;
          toast('Setup failed', { description: detail ?? 'An unexpected error occurred' });
        },
      },
    );
  };

  if (isLoading) return null;

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: '#2D2D2D' }}>
      <div className="w-full max-w-md rounded-2xl bg-white text-black shadow-2xl overflow-hidden">
        <div className="px-8 py-6 text-center" style={{ backgroundColor: '#E5E5E5' }}>
          <div
            className="w-20 h-20 mx-auto mb-4 rounded-full flex items-center justify-center"
            style={{ backgroundColor: '#BF0000' }}
          >
            <User className="size-10 text-white" />
          </div>
          <h1 className="text-2xl font-bold mb-1">Welcome to Code Sense</h1>
          <p className="text-sm text-gray-600">Create the administrator account to get started.</p>
        </div>

        <form className="px-8 py-8 space-y-5" onSubmit={submit}>
          <div>
            <label className="block text-sm font-medium mb-2">Full name</label>
            <Input value={form.name} onChange={onChange('name')} required placeholder="Jane Admin" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#BF0000' }} />
              <Input
                type="email"
                value={form.email}
                onChange={onChange('email')}
                required
                className="pl-9"
                placeholder="admin@company.com"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Company (optional)</label>
            <Input value={form.company} onChange={onChange('company')} placeholder="Acme Inc." />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#BF0000' }} />
              <Input
                type="password"
                value={form.password}
                onChange={onChange('password')}
                required
                className="pl-9"
                placeholder="Choose a strong password"
              />
            </div>
          </div>

          <Button type="submit" disabled={createAdmin.isPending} className="w-full py-5">
            {createAdmin.isPending ? 'Creating…' : 'Create administrator'}
          </Button>
        </form>
      </div>
    </div>
  );
}
