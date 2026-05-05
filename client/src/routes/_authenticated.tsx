import Header from '@/components/molecule/header'
import Sidebar from '@/components/molecule/sidebar'
import { createFileRoute, Outlet } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated')({
  component: RouteComponent,
})

function RouteComponent() {
  
  return (
    <div className='flex h-screen overflow-hidden bg-background'>
      {/* Fixed Sidebar */}
      <div className='fixed left-0 top-0 h-full z-10'>
        <Sidebar />
      </div>
      
      {/* Main content area with margin to account for fixed sidebar */}
      <div className='flex flex-col w-full ml-64'> {/* Adjust ml-64 based on your sidebar width */}
        {/* Fixed Header */}
        <div className='fixed top-0 right-0 left-64 z-20'> {/* Adjust left-64 based on your sidebar width */}
          <Header />
        </div>
        
        {/* Scrollable content area */}
        <div className='flex-1 p-4 mt-16 overflow-y-auto'> {/* Adjust mt-16 based on your header height */}
          <Outlet /> 
        </div>
      </div>
    </div>
  )
}