import { createFileRoute, useParams } from '@tanstack/react-router';
import { ApiKeysPanel } from '@/components/update/ApiKeysPanel';

export const Route = createFileRoute('/_authenticated/project/$projectId/settings')({
  component: RouteComponent,
})

function RouteComponent() {
  const { projectId } = useParams({ from: '/_authenticated/project/$projectId/settings' });
  return <ApiKeysPanel projectId={projectId} />;
}
