export function DotsLoader() {
  return (
    <div className="w-full h-full flex items-center justify-center">
      <div className="flex space-x-2">
        <div
          className="w-3 h-3 rounded-full animate-bounce"
          style={{
            backgroundColor: '#bf0000',
            animationDelay: '0ms'
          }}>
        </div>
        <div
          className="w-3 h-3 rounded-full animate-bounce"
          style={{
            backgroundColor: '#bf0000',
            animationDelay: '150ms'
          }}>
        </div>
        <div
          className="w-3 h-3 rounded-full animate-bounce"
          style={{
            backgroundColor: '#bf0000',
            animationDelay: '300ms'
          }}>
        </div>
      </div>
    </div>
  );
}