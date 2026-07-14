import { createRootRoute, Outlet } from '@tanstack/react-router'
import { Toaster } from "@/components/atomic/sonner"
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAssetSetup } from '@/hooks/use-asset-setup';
import { FirstRunSetup } from '@/components/setup/FirstRunSetup';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute
      retry: 1,
    },
  },
});

function RootComponent() {
  const assetSetup = useAssetSetup();

  return (
    <QueryClientProvider client={queryClient}>
      {assetSetup.status === 'ready' ? <Outlet /> : <FirstRunSetup state={assetSetup} />}
      <Toaster />
    </QueryClientProvider>
  );
}

export const Route = createRootRoute({
  component: RootComponent,
})