import { DotsLoader } from '@/components/atomic/loader';
import ScanUpdate from '@/components/update/Scanupdate';
import { useScanDetails } from '@/hooks/use-scans';
import { createFileRoute, useParams } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/scan/$scanId/updates')({
  component: UpdatesComponent,
})

function UpdatesComponent() {
  const { scanId } = useParams({ from: '/_authenticated/scan/$scanId/updates' });
  const { data, isLoading } = useScanDetails(scanId)

  if(isLoading) return <DotsLoader />

  return (
    <div>
      <ScanUpdate scan={data}/>
    </div>
  );
}