import { useEffect } from 'react'
import { generateBrandPalette } from '@/lib/colorUtils'
import { useAuthStore } from '@/store/authStore'

export default function BrandingProvider({ children }) {
  const { school } = useAuthStore()

  useEffect(() => {
    const primary = school?.primary_color || '#1e40af'
    const secondary = school?.secondary_color || '#ffffff'
    const accent = school?.accent_color || '#fbbc04'
    const palette = generateBrandPalette(primary)
    const root = document.documentElement

    root.style.setProperty('--brand-primary', palette.primary)
    root.style.setProperty('--brand-primary-hover', palette.primaryHover)
    root.style.setProperty('--brand-primary-light', palette.primaryLight)
    root.style.setProperty('--brand-primary-ring', palette.primaryRing)
    root.style.setProperty('--brand-secondary', secondary)
    root.style.setProperty('--brand-accent', accent)

    if (school?.logo) {
      let link = document.querySelector("link[rel~='icon']")
      if (!link) {
        link = document.createElement('link')
        link.rel = 'icon'
        document.head.appendChild(link)
      }
      link.href = school.logo
    }

    if (school?.name) {
      document.title = `${school.name} - School Management`
    }
  }, [school])

  return children
}