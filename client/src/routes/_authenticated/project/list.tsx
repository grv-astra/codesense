import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { GenericTable, type TableColumn } from '@/components/molecule/generic-table';
import { Button } from '@/components/atomic/button';
import { Edit, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { formatTimestamp } from '@/utils/timestampFormater';
import { useDeleteProject, useProjects } from '@/hooks/use-project';
import type { ProjectDetails } from '@/types/project';
import { ConfirmDialog } from '@/components/atomic/dialog-confirm';

export const Route = createFileRoute('/_authenticated/project/list')({
  component: RouteComponent,
});


function RouteComponent() {
  const navigate = useNavigate()
  const usersPerPage = 10;
  const [currentPage, setCurrentPage] = useState(1);

  // For server-side pagination
  const { data: projectResponse, isLoading, error } = useProjects({
    page: currentPage,
    limit: usersPerPage,
  });
  const deletedProjectMutation = useDeleteProject()

  const projects = projectResponse?.projects || [];
  const totalProjects = projectResponse?.pagination.total || 0;

  // Define table columns
  const projectColumns: TableColumn<ProjectDetails>[] = [
    {
      key: 'srNo',
      header: 'Sr No.',
      render: (_, index: number) => index + 1,
      width: '80px'
    },
    {
      key: 'name',
      header: 'Project Name',
      sortable: true
    },
    {
      key: 'preset',
      header: 'Preset'
    },
    {
      key: 'created_at',
      header: 'Created At',
      render: (project) => (
        <p>{formatTimestamp(project.created_at)}</p>
      )
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (project) => (
        <div className="flex space-x-2">
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              handleEdit(project);
            }}
          >
            <Edit className="w-4 h-4" />
          </Button>
          <ConfirmDialog
            trigger={
              <Button size="sm" variant="outline" className="text-red-600 hover:text-red-700">
                <Trash2 className="w-4 h-4" />
              </Button>
            }
            title="Delete User"
            description="This action cannot be undone. This will permanently delete the user
                  and remove your data from our servers."
            confirmLabel="Delete"
            cancelLabel="Cancel"
            confirmText={project.name}
            onConfirm={() => handleDelete(project)}
          />
        </div>
      ),
      width: '150px'
    }
  ];

  const handleEdit = (project: ProjectDetails) => {
    navigate({from: '/project/list', to: `../${project.id}/edit`})
  };

  const handleDelete = async (project: ProjectDetails) => {
    await deletedProjectMutation.mutateAsync(project.id)
  };

  const handleRowClick = (project: ProjectDetails) => {
    navigate({from: '/project/list', to: `../${project.id}`})
  };

  return (
    <GenericTable
      data={projects}
      columns={projectColumns}
      title="Projects List"
      loading={isLoading}
      error={error?.message}
      pagination={{
        enabled: true,
        pageSize: usersPerPage,
        showInfo: true,
        showPageNumbers: true
      }}
      totalItems={totalProjects}
      currentPage={currentPage}
      onPageChange={setCurrentPage}
      emptyMessage="No projects found"
      onRowClick={handleRowClick}
      rowClassName={() => 
        `hover:bg-gray-50 hover:dark:bg-gray-300/10`
      }
    />
  );
}