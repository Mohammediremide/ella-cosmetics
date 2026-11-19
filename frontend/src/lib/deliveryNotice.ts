export function isLateNightOrderNotice(date = new Date(), timeZone = 'Africa/Lagos'): boolean {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const hour = Number(parts.find((part) => part.type === 'hour')?.value ?? 0)
  return hour >= 20 || hour < 5
}
