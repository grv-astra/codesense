import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/project/$projectId/')({
  beforeLoad: ({ params }) => {
      // Redirect to updates tab by default
      throw redirect({
        to: '/project/$projectId/codescan',
        params: { projectId: params.projectId },
      });
    },
})
