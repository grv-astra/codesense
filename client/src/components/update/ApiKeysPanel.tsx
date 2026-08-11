import { useState } from 'react';
import { toast } from 'sonner';
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

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const key = await onCreate(name.trim());
      setRevealedKey(key);
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
            <code className="block break-all rounded bg-muted p-2 text-sm">{revealedKey}</code>
            <DialogFooter>
              <Button
                onClick={() => {
                  navigator.clipboard.writeText(revealedKey);
                  toast('Copied to clipboard');
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
        <h2 className="text-lg font-semibold">CI API Keys</h2>
        <Button onClick={() => setDialogOpen(true)}>Generate new key</Button>
      </div>

      {isLoading && <p>Loading...</p>}
      {!isLoading && (!keys || keys.length === 0) && (
        <p className="text-muted-foreground text-sm">No API keys yet.</p>
      )}
      {!isLoading && keys && keys.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th>Name</th>
              <th>Prefix</th>
              <th>Created</th>
              <th>Last used</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {keys.map((key) => (
              <tr key={key.id}>
                <td>{key.name}</td>
                <td>{key.key_prefix}...</td>
                <td>{new Date(key.created_at).toLocaleDateString()}</td>
                <td>{key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'}</td>
                <td>{key.revoked_at ? 'Revoked' : 'Active'}</td>
                <td>
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
      )}

      <GenerateKeyDialog open={dialogOpen} onOpenChange={setDialogOpen} onCreate={handleCreate} />
    </div>
  );
}
