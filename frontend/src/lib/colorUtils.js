export function adjustColor(hex, percent) {
  let value = hex.replace('#', '')
  if (value.length === 3) {
    value = value.split('').map((char) => char + char).join('')
  }

  const num = parseInt(value, 16)
  const amount = Math.round(255 * (percent / 100))
  const r = Math.max(0, Math.min(255, (num >> 16) + amount))
  const g = Math.max(0, Math.min(255, ((num >> 8) & 0x00ff) + amount))
  const b = Math.max(0, Math.min(255, (num & 0x0000ff) + amount))

  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`
}

export function generateBrandPalette(primaryColor) {
  return {
    primary: primaryColor,
    primaryHover: adjustColor(primaryColor, -12),
    primaryLight: adjustColor(primaryColor, 88),
    primaryRing: `${primaryColor}33`,
  }
}

export function getContrastText(hex) {
  const value = hex.replace('#', '')
  const normalized = value.length === 3
    ? value.split('').map((char) => char + char).join('')
    : value
  const r = parseInt(normalized.slice(0, 2), 16)
  const g = parseInt(normalized.slice(2, 4), 16)
  const b = parseInt(normalized.slice(4, 6), 16)
  const brightness = (r * 299 + g * 587 + b * 114) / 1000

  return brightness > 155 ? '#000000' : '#ffffff'
}
