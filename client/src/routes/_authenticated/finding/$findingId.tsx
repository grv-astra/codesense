import { DotsLoader } from '@/components/atomic/loader';
import Finding from '@/components/update/UpdatedFinding'
import { useFindingDetails } from '@/hooks/use-finding'
import { createFileRoute, useParams } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/finding/$findingId')({
  component: RouteComponent,
})

function RouteComponent() {
  const { findingId } = useParams({ from: '/_authenticated/finding/$findingId' });

  const { data, isLoading } = useFindingDetails(findingId)

  if (isLoading) return <DotsLoader />
  return <Finding finding={data}/>
}
 