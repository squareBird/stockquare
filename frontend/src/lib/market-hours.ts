// Korean stock market hours helper.
// KOSPI/KOSDAQ regular session: 09:00 – 15:30 KST, Monday–Friday.

const KST_OFFSET_MINUTES = 9 * 60;

export function isMarketHours(date: Date = new Date()): boolean {
  // Compute day-of-week and time of day in KST regardless of the host timezone.
  const utcMinutes = date.getUTCHours() * 60 + date.getUTCMinutes();
  const totalKstMinutes = utcMinutes + KST_OFFSET_MINUTES;
  const dayOffset = Math.floor(totalKstMinutes / (24 * 60));
  const minutesInKstDay = ((totalKstMinutes % (24 * 60)) + 24 * 60) % (24 * 60);

  const kstDayOfWeek = (date.getUTCDay() + dayOffset + 7) % 7;
  if (kstDayOfWeek === 0 || kstDayOfWeek === 6) return false;

  const openMinutes = 9 * 60;
  const closeMinutes = 15 * 60 + 30;
  return minutesInKstDay >= openMinutes && minutesInKstDay < closeMinutes;
}
