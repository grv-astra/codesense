import { Button } from '@/components/atomic/button';
import { DotsLoader } from '@/components/atomic/loader';
import Finding from '@/components/update/UpdatedFinding'
import { useFindingDetails } from '@/hooks/use-finding'
import { createFileRoute, useParams, useRouter } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/finding/$findingId')({
  component: RouteComponent,
})

function RouteComponent() {
  const { findingId } = useParams({ from: '/_authenticated/finding/$findingId' });
  const router = useRouter();

  const { data, isLoading } = useFindingDetails(findingId)

  if (isLoading) return <DotsLoader />
  return (
    <div className="p-2">
      <Button variant="ghost" type="button" onClick={() => router.history.back()}>
        ←  Back to Findings
      </Button>
      <Finding finding={data} />
    </div>
  )
}
 