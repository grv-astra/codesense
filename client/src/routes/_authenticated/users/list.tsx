import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { GenericTable, type TableColumn } from '@/components/molecule/generic-table';
import { Button } from '@/components/atomic/button';
import { Edit, Trash2 } from 'lucide-react';
import { useState } from 'react';
import type { User } from '@/types/auth';
import { RoleBadge } from '@/components/atomic/enum-badge';
import { useDeleteProfile, useUsers } from '@/hooks/use-user';
import { ConfirmDialog } from '@/components/atomic/dialog-confirm';

export const Route = createFileRoute('/_authenticated/users/list')({
  component: RouteComponent,
});


function RouteComponent() {
  const usersPerPage = 10;
  const [currentPage, setCurrentPage] = useState(1);
  const navigate = useNavigate({ from: '/users/list' })

  // For server-side pagination
  const { data: usersResponse, isLoading, error } = useUsers({
    page: currentPage,
    limit: usersPerPage,
  });
  const deleteUserMutation = useDeleteProfile()

  const users = usersResponse?.users || [];
  const totalUsers = usersResponse?.pagination.total || 0;

  // Define table columns
  const userColumns: TableColumn<User>[] = [
    {
      key: 'srNo',
      header: 'Sr No.',
      render: (_, index: number) => index + 1,
      width: '80px'
    },
    {
      key: 'name',
      header: 'Username',
      sortable: true
    },
    {
      key: 'email',
      header: 'Email'
    },
    {
      key: 'company',
      header: 'Company'
    },
    {
      key: 'role',
      header: 'Role',
      render: (user) => (
        <RoleBadge role={user.role}/>
      )
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (user) => (
        <div className="flex space-x-2">
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              handleEdit(user);
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
            onConfirm={() => handleDelete(user)}
          />

        </div>
      ),
      width: '150px'
    }
  ];

  const handleEdit = (user: User) => {
    navigate({ to: `/users/${user.id}/edit`})
  };

  const handleDelete = async (user: User) => {
    try {
      await deleteUserMutation.mutateAsync(user.id)
    } catch (error) {
      console.error("Error deleting user: " + user.name)
    }
    
  };

  const handleRowClick = (user: User) => {
    console.log('View user:', user);
  };

  return (
    <GenericTable
      data={users}
      columns={userColumns}
      title="User List"
      loading={isLoading}
      error={error?.message}
      pagination={{
        enabled: true,
        pageSize: usersPerPage,
        showInfo: true,
        showPageNumbers: true
      }}
      totalItems={totalUsers}
      currentPage={currentPage}
      onPageChange={setCurrentPage}
      emptyMessage="No users found"
      onRowClick={handleRowClick}
      rowClassName={() => 
        `hover:bg-gray-50 hover:dark:bg-gray-300/10`
      }
    />
  );
}