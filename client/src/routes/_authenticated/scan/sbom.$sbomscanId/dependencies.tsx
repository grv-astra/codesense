import { StateBadge } from '@/components/atomic/enum-badge';
import { GenericTable, type TableColumn } from '@/components/molecule/generic-table';
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react';

export const Route = createFileRoute(
  '/_authenticated/scan/sbom/$sbomscanId/dependencies',
)({
  component: RouteComponent,
})

export interface DependenceDetails {
  id: string;
  package_name: string;
  dependence_version: string;
  risk_rating: string;
  risk_summary: string;
}

const STATIC_DEPENDENCIES: DependenceDetails[] = [
  {
    id: '1',
    package_name: 'lodash',
    dependence_version: '4.17.15',
    risk_rating: 'high',
    risk_summary: 'Prototype pollution vulnerability detected in merge functions.',
  },
  {
    id: '2',
    package_name: 'express',
    dependence_version: '4.18.2',
    risk_rating: 'low',
    risk_summary: 'No known critical vulnerabilities. Minor dependency updates recommended.',
  },
  {
    id: '3',
    package_name: 'axios',
    dependence_version: '0.21.1',
    risk_rating: 'medium',
    risk_summary: 'SSRF vulnerability found in redirect handling.',
  },
  {
    id: '4',
    package_name: 'moment',
    dependence_version: '2.29.1',
    risk_rating: 'low',
    risk_summary: 'Package is in maintenance mode. Consider migrating to date-fns.',
  },
  {
    id: '5',
    package_name: 'jsonwebtoken',
    dependence_version: '8.5.1',
    risk_rating: 'critical',
    risk_summary: 'Improper signature validation allows token forgery.',
  },
  {
    id: '6',
    package_name: 'webpack',
    dependence_version: '5.75.0',
    risk_rating: 'low',
    risk_summary: 'No significant vulnerabilities. Up to date.',
  },
  {
    id: '7',
    package_name: 'react-dom',
    dependence_version: '18.2.0',
    risk_rating: 'low',
    risk_summary: 'Stable release with no known security issues.',
  },
];

function RouteComponent() {
  const navigate = useNavigate();
  const itemsPerPage = 10;
  const [currentPage, setCurrentPage] = useState(1);
  const [dependencies] = useState<DependenceDetails[]>(STATIC_DEPENDENCIES);

  const dependenceColumns: TableColumn<DependenceDetails>[] = [
    {
      key: 'srNo',
      header: 'Sr No.',
      render: (_, index: number) => index + 1,
      width: '80px',
    },
    {
      key: 'package_name',
      header: 'Package Name',
      sortable: true,
    },
    {
      key: 'dependence_version',
      header: 'Version',
    },
    {
      key: 'risk_rating',
      header: 'Risk Rating',
      render: (dep) => (
        <StateBadge state={dep.risk_rating} />
      ),
    },
    {
      key: 'risk_summary',
      header: 'Risk Summary',
    },
  ];

  const handleRowClick = (dep: DependenceDetails) => {
    navigate({ to: `/scan/sbom/${dep.id}` });
  };

  return (
    <GenericTable
      data={dependencies}
      columns={dependenceColumns}
      title="Dependencies List"
      loading={false}
      error={undefined}
      pagination={{
        enabled: true,
        pageSize: itemsPerPage,
        showInfo: true,
        showPageNumbers: true,
      }}
      totalItems={dependencies.length}
      currentPage={currentPage}
      onPageChange={setCurrentPage}
      emptyMessage="No dependencies found"
      onRowClick={handleRowClick}
      rowClassName={() => `hover:bg-gray-50 hover:dark:bg-gray-300/10`}
      enableColumnFilter={true}
      filterButtonVariant="outline"
    />
  );
}