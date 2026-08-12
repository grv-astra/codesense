import { DotsLoader } from '@/components/atomic/loader';

// Shown for the brief window between assets being ready and the one-time
// activation check resolving. Previously rendered nothing at all here (to
// avoid a login-page flash), which looked like a hung/broken blank gray
// screen -- same dark shell + card as FirstRunSetup so it reads as "still
// starting up" rather than "something crashed".
export function CheckingActivation() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: '#2D2D2D' }}>
      <div className="w-full max-w-md rounded-2xl bg-white text-black shadow-2xl overflow-hidden px-8 py-10 text-center space-y-4">
        <div className="h-10">
          <DotsLoader />
        </div>
        <p className="text-sm text-gray-600">Starting Code Sense…</p>
      </div>
    </div>
  );
}
