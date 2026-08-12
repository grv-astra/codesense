import { createFileRoute, useParams } from '@tanstack/react-router';
import { ApiKeysPanel } from '@/components/update/ApiKeysPanel';
import { ProjectOverview } from '@/components/update/ProjectOverview';

export const Route = createFileRoute('/_authenticated/project/$projectId/settings')({
  component: RouteComponent,
})

function RouteComponent() {
  const { projectId } = useParams({ from: '/_authenticated/project/$projectId/settings' });
  return (
    <div className="space-y-8">
      <ProjectOverview projectId={projectId} />
      <div className="border-t pt-6">
        <ApiKeysPanel projectId={projectId} />
      </div>
    </div>
  );
}
