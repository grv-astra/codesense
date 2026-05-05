import { createFileRoute } from '@tanstack/react-router'
import { useAuth } from '@/hooks/use-auth'
import { formatTimestamp } from '@/utils/timestampFormater'
import { DotsLoader } from '@/components/atomic/loader'
import {
  Building2,
  Mail,
  ShieldCheck,
  CalendarDays,
  RefreshCw,
} from 'lucide-react'

export const Route = createFileRoute('/_authenticated/profile')({
  component: RouteComponent,
})

function Field({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">{label}</p>
      <p className="text-sm font-medium text-foreground capitalize">{value ?? '—'}</p>
    </div>
  )
}

function RouteComponent() {
  const { user, isLoading, error } = useAuth()

  if (isLoading) return <DotsLoader />
  if (error) return <div className="p-6 text-red-600">Error: {error.message}</div>

  const initials = user?.name
    ? user.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
    : '??'

  return (
    <div className="min-h-screen p-6 md:p-10">
      <div className="max-w-7xl mx-auto">
        <div className="rounded-xl border bg-card overflow-hidden ">

          {/* Sidebar */}
          <div className="shrink-0  border-r flex justify-between items-center py-8 px-10 gap-4 bg-primary/10">
            {/* Avatar */}
            <div className='flex items-center gap-4'>
            <div className="h-18 w-18 rounded-full bg-primary/20 border-2 border-primary/30 flex items-center justify-center text-2xl font-semibold text-primary select-none" style={{ width: 72, height: 72 }}>
              {initials}
            </div>
            <div className="text-left">
              <p className="text-lg font-semibold text-foreground capitalize">{user?.name}</p>
              <p className="text-sm text-muted-foreground capitalize mt-0.5">{user?.company}</p>
            </div>
            </div>
            <span className="text-md font-medium px-3 py-1 rounded-full bg-red-500/10 text-red-600 border border-red-500/20 capitalize">
              {user?.role}
            </span>  
          </div>

          {/* Main content */}
          <main className="flex-1 p-8">
            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-5">
              Personal Info
            </p>

            <div className="grid grid-cols-2 gap-x-8 gap-y-6 mb-8">
              <Field label="Full Name" value={user?.name} />
              <Field label="Company" value={user?.company} />
              <Field label="Email" value={user?.email} />
              <Field label="Role" value={user?.role} />
            </div>

            <div className="h-px bg-border mb-8" />

            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">
              Account Timeline
            </p>

            <div className="grid grid-cols-3 gap-3">
              {[
                { icon: CalendarDays, label: 'Member since', value: formatTimestamp(user?.created_at) },
                { icon: RefreshCw, label: 'Last updated', value: formatTimestamp(user?.updated_at) },
                { icon: ShieldCheck, label: 'Status', value: 'Active', green: true },
              ].map(({ icon: Icon, label, value, green }) => (
                <div key={label} className="bg-muted rounded-lg px-3 py-3 flex flex-col gap-1">
                  <div className="flex items-center gap-1.5 text-muted-foreground">
                    <Icon size={16} />
                    <p className="text-xs">{label}</p>
                  </div>
                  <p className={`text-sm font-medium ${green ? 'text-red-600' : 'text-foreground'}`}>
                    {value}
                  </p>
                </div>
              ))}
            </div>

            <div className="h-px bg-border my-8" />

            <div className="flex items-center gap-3 p-4 rounded-lg bg-muted border">
              <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                <Building2 size={20} className="text-primary" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Workspace</p>
                <p className="text-sm font-medium text-foreground capitalize">{user?.company}</p>
              </div>
              <div className="ml-auto">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Mail size={20} className="text-primary" />
                </div>
              </div>
            </div>
          </main>

        </div>
      </div>
    </div>
  )
}
 