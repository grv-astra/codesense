import { Link } from '@tanstack/react-router';
import { Badge } from '@/components/atomic/badge';
import { Button } from '@/components/atomic/button';
import { DotsLoader } from '@/components/atomic/loader';
import { useProjectDetails } from '@/hooks/use-project';

export function ProjectOverview({ projectId }: { projectId: string }) {
  const { data: project, isLoading } = useProjectDetails(projectId);

  if (isLoading) {
    return <DotsLoader />;
  }

  if (!project) {
    return <p className="text-muted-foreground text-sm">Could not load project details.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">{project.name}</h1>
            {project.preset && <Badge variant="secondary">{project.preset}</Badge>}
          </div>
          {project.description && (
            <p className="text-sm text-muted-foreground mt-1 max-w-2xl">{project.description}</p>
          )}
        </div>
        <Link to="/project/$projectId/edit" params={{ projectId }}>
          <Button variant="outline" size="sm">Edit Project</Button>
        </Link>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm border-t pt-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">
            Project ID
          </div>
          <div className="font-mono text-xs break-all">{project.id}</div>
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">
            Created
          </div>
          <div>{new Date(project.created_at).toLocaleDateString()}</div>
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">
            Last updated
          </div>
          <div>{project.updated_at ? new Date(project.updated_at).toLocaleDateString() : '—'}</div>
        </div>
      </div>
    </div>
  );
}
