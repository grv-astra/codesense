import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/scan/sbom/$sbomscanId/')({
  beforeLoad: ({ params }) => {
      // Redirect to updates tab by default
      throw redirect({
        to: '/scan/sbom/$sbomscanId/updates',
        params: { sbomscanId: params.sbomscanId },
      });
    },
})

