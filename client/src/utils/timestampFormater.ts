/**
 * Converts an ISO timestamp with microseconds to a human-readable IST format.
 *
 * @param isoTimestamp - A timestamp like "2025-07-27T14:51:36.689000"
 * @param options - Optional Intl.DateTimeFormat options (only affects month/day/year formatting)
 * @returns A readable date string in IST, e.g., "July 27, 2025, 8:21:36 PM IST"
 */
export function formatTimestamp(
  isoTimestamp: string | undefined | null,
  options: Intl.DateTimeFormatOptions = {}
): string {
  if (!isoTimestamp || typeof isoTimestamp !== 'string') return '';
 
  // Remove last 3 digits from microseconds to fit JS Date format (milliseconds)
  const cleaned = isoTimestamp.slice(0, -3); // e.g., "2025-07-27T14:51:36.689"
  const date = new Date(cleaned);
 
  if (isNaN(date.getTime())) return '';
 
  // Convert UTC to IST (+5:30 hours)
  const istOffsetMs = 5.5 * 60 * 60 * 1000; // 5 hours 30 mins in ms
  const istDate = new Date(date.getTime() + istOffsetMs);
 
  // Extract components
  const day = istDate.getDate().toString().padStart(2, '0');
  const month = istDate.toLocaleString("en-US", { month: "short", ...options });
  const year = istDate.getFullYear();
 
  let hours = istDate.getHours();
  const minutes = istDate.getMinutes().toString().padStart(2, '0');
  const strHours = hours.toString().padStart(2, '0');
 
  return ` ${strHours}:${minutes} - ${month}. ${day}, ${year}`;
}
 