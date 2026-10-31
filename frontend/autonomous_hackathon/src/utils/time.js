// Destination-local minutes since midnight, including next-day values.
export function formatMinute(value) {
  if (value == null) return '—'
  const day = Math.floor(value / 1440)
  const minute = ((value % 1440) + 1440) % 1440
  const time = `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`
  return day ? `${time} (${day > 0 ? '+' : ''}${day}d)` : time
}
