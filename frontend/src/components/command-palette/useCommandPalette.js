import { useState, useEffect, useCallback } from 'react'

export function useCommandPalette() {
  const [open, setOpen] = useState(false)

  const toggle = useCallback(() => setOpen(v => !v), [])
  const close = useCallback(() => setOpen(false), [])

  useEffect(() => {
    const handleKeyDown = (e) => {
      // Open on Cmd/Ctrl + K
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(true)
      }
      
      // Escape closes out the palette
      if (e.key === 'Escape') {
        setOpen(false)
      }
    }

    // Notice the `true` argument added to both listeners below (Capture phase)
    window.addEventListener('keydown', handleKeyDown, true)
    return () => window.removeEventListener('keydown', handleKeyDown, true)
  }, [])

  return { open, setOpen, toggle, close }
}