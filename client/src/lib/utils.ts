import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// navigator.clipboard only exists in "secure contexts" -- HTTPS, or
// localhost specifically exempted even over plain HTTP. Any other
// IP/hostname over HTTP (e.g. reaching this app via a LAN IP instead of
// localhost) isn't a secure context, so the API is undefined there and
// silently does nothing. Falls back to the legacy execCommand('copy') path
// (a temporary offscreen textarea) whenever the modern API isn't available.
export async function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fall through to the legacy path below
    }
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  textarea.style.top = '0';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  let succeeded = false;
  try {
    succeeded = document.execCommand('copy');
  } catch {
    succeeded = false;
  }
  document.body.removeChild(textarea);
  return succeeded;
}
