import { createRouter, RouterProvider } from '@tanstack/react-router'
import './App.css'
 
import { routeTree } from './routeTree.gen'
import { ThemeProvider } from './contexts/use-theme'
 
// Create a new router instance
const router = createRouter({ routeTree })
 
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
 
function App() {
  return (
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  )
}
 
export default App