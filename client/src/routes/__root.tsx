import { createRootRoute, Outlet } from '@tanstack/react-router'
import { Toaster } from "@/components/atomic/sonner"
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAssetSetup } from '@/hooks/use-asset-setup';
import { useActivation } from '@/hooks/use-activation';
import { FirstRunSetup } from '@/components/setup/FirstRunSetup';
import { ActivationGate } from '@/components/setup/ActivationGate';

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
  const activation = useActivation();

  let body: React.ReactNode;
  if (assetSetup.status !== 'ready') {
    body = <FirstRunSetup state={assetSetup} />;
  } else if (activation.state.status === 'locked') {
    body = <ActivationGate error={activation.error} submitting={activation.submitting} onSubmit={activation.submit} />;
  } else if (activation.state.status === 'checking') {
    body = null; // avoid a login-page flash while the one-time check is in flight
  } else {
    body = <Outlet />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      {body}
      <Toaster />
    </QueryClientProvider>
  );
}

export const Route = createRootRoute({
  component: RootComponent,
})