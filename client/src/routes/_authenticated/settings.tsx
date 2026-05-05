import AccessControlSystem from '@/components/update/access-control'
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/settings')({
  component: RouteComponent,
})

function RouteComponent() {
  return <AccessControlSystem />
}
