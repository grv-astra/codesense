import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Badge } from '@/components/atomic/badge';
import { Button } from '@/components/atomic/button';
import { Input } from '@/components/atomic/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/atomic/dialog';
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '@/hooks/use-api-keys';
import { copyToClipboard } from '@/lib/utils';

function GenerateKeyDialog({
  open,
  onOpenChange,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (name: string) => Promise<string>;
}) {
  const [name, setName] = useState('');
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const activeRef = useRef(open);

  useEffect(() => {
    activeRef.current = open;
  }, [open]);

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const key = await onCreate(name.trim());
      if (activeRef.current) {
        setRevealedKey(key);
      }
    } catch {
      if (activeRef.current) {
        toast('Failed to generate key', {
          description: 'Could not create the API key. Please try again.',
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = (nextOpen: boolean) => {
    if (!nextOpen) {
      setName('');
      setRevealedKey(null);
    }
    onOpenChange(nextOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        {!revealedKey ? (
          <>
            <DialogHeader>
              <DialogTitle>Generate CI API key</DialogTitle>
              <DialogDescription>
                Name this key so you can identify it later, e.g. "azure-devops-prod".
              </DialogDescription>
            </DialogHeader>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Key name"
              aria-label="Key name"
            />
            <DialogFooter>
              <Button onClick={handleSubmit} disabled={submitting || !name.trim()}>
                Generate
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Your new API key</DialogTitle>
              <DialogDescription>
                Copy this key now — you won't be able to see it again.
              </DialogDescription>
            </DialogHeader>
            <input
              readOnly
              value={revealedKey}
              onFocus={(e) => e.currentTarget.select()}
              className="block w-full break-all rounded bg-muted p-2 text-sm font-mono"
              aria-label="Generated API key"
            />
            <DialogFooter>
              <Button
                onClick={async () => {
                  const ok = await copyToClipboard(revealedKey);
                  if (ok) {
                    toast('Copied to clipboard');
                  } else {
                    toast('Could not copy', { description: 'Select and copy the key manually.' });
                  }
                }}
              >
                Copy
              </Button>
              <Button variant="outline" onClick={() => handleClose(false)}>
                Done
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function ApiKeysPanel({ projectId }: { projectId: string }) {
  const { data: keys, isLoading } = useApiKeys(projectId);
  const createKey = useCreateApiKey(projectId);
  const revokeKey = useRevokeApiKey(projectId);
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleCreate = async (name: string) => {
    const result = await createKey.mutateAsync({ name });
    return result.key;
  };

  const handleRevoke = async (keyId: string) => {
    try {
      await revokeKey.mutateAsync(keyId);
      toast('API key revoked');
    } catch {
      toast('Failed to revoke key', {
        description: 'Could not revoke the API key. Please try again.',
      });
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">CI API Keys</h2>
          <p className="text-sm text-muted-foreground">
            Let CI/CD pipelines trigger scans for this project without a human login.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>Generate new key</Button>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
      {!isLoading && (!keys || keys.length === 0) && (
        <p className="text-muted-foreground text-sm border rounded-lg p-6 text-center">
          No API keys yet.
        </p>
      )}
      {!isLoading && keys && keys.length > 0 && (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground bg-muted/50">
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Prefix</th>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2 font-medium">Last used</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="sr-only">Actions</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id} className="border-t">
                  <td className="px-4 py-3 font-medium">{key.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {key.key_prefix}...
                  </td>
                  <td className="px-4 py-3">{new Date(key.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    {key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'}
                  </td>
                  <td className="px-4 py-3">
                    {key.revoked_at ? (
                      <Badge variant="outline">Revoked</Badge>
                    ) : (
                      <Badge variant="secondary">Active</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {!key.revoked_at && (
                      <Button size="sm" variant="outline" onClick={() => handleRevoke(key.id)}>
                        Revoke
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <GenerateKeyDialog open={dialogOpen} onOpenChange={setDialogOpen} onCreate={handleCreate} />
    </div>
  );
}
