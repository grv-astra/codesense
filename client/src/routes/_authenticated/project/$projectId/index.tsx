import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/project/$projectId/')({
  beforeLoad: ({ params }) => {
      // Redirect to the overview tab by default
      throw redirect({
        to: '/project/$projectId/settings',
        params: { projectId: params.projectId },
      });
    },
})
