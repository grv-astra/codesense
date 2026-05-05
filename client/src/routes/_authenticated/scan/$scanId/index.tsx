import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/scan/$scanId/')({
  beforeLoad: ({ params }) => {
    // Redirect to updates tab by default
    throw redirect({
      to: '/scan/$scanId/updates',
      params: { scanId: params.scanId },
    });
  },
})