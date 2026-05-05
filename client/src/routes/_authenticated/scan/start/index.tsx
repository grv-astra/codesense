import { Card } from '@/components/atomic/card'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { Upload, Github } from 'lucide-react'

export const Route = createFileRoute('/_authenticated/scan/start/')({
  component: RouteComponent,
})

function RouteComponent() {
  const navigate = useNavigate()

  const options = [
    { 
      id: 'zip', 
      label: 'Upload Zip', 
      icon: Upload,
      description: 'Upload a compressed file',
      route: '/scan/start/uploadzip'
    },
    { 
      id: 'github', 
      label: 'GitHub', 
      icon: Github,
      description: 'Connect from GitHub',
      route: '/scan/start/githubrepo'
    },
    { 
      id: 'zip', 
      label: 'Upload SBOM File', 
      icon: Upload,
      description: 'Upload a compressed file',
      route: '/scan/start/uploadsbom'
    },
  ]

  const handleSelection = (route: string) => {
    navigate({ to: route })
  }

  return (
    
    <div className="p-6 max-w-8xl mx-auto">
      <Card className="shadow-lg rounded-lg">
        <div className='xl:px-52 py-20 px-20'>
          <div className="text-center mb-12">
            <h1 className="text-4xl font-bold">
              Connect Your Repository
            </h1>
            <p className="">
              Select a source and provide the details
            </p>
          </div>

          <div className="grid xl:grid-cols-2 lg:grid-cols-1 gap-7">
          {options.map((opt) => {
            const Icon = opt.icon
            const isDisabled = opt.id === 'azure' // 👈 disable here

            return (
              <div
                key={opt.id}
                onClick={() => {
                  if (isDisabled) return // 👈 block click0
                  handleSelection(opt.route)
                }}
                className={`flex items-center justify-between p-8 group rounded-md border-0 shadow-sm transition-all duration-200 relative overflow-hidden
                ${isDisabled 
                  ? 'bg-gray-200 dark:bg-[#3b3b3b] opacity-50 cursor-not-allowed' 
                  : 'bg-[#f1f1f1] dark:bg-[#3b3b3b] hover:shadow-md hover:bg-gradient-to-br from-red-500/30 to-red-600/20 cursor-pointer'
                }`}
              >
                <div>
                  <p className="text-lg font-semibold mb-2">
                    {opt.label}
                    {isDisabled && (
                      <span className="ml-2 text-xs text-red-500">
                        (Coming Soon)
                      </span>
                    )}
                  </p>
                  <p className="text-sm text-gray-400">
                    {opt.description}
                  </p>
                </div>

                <div className={`p-2 rounded-md shadow-sm transition-all duration-300
                  ${isDisabled 
                    ? 'bg-gray-400 dark:bg-[#505050]' 
                    : 'bg-red-900 dark:bg-red-800 group-hover:scale-110'
                  }`}
                >
                  <Icon size={35} className="text-white" />
                </div>
              </div>
            )
          })}
        </div>
        </div>
      </Card>
    </div>
  )
}