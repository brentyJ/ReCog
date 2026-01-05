/**
 * Scanlines Overlay Component
 * 
 * Adds subtle CRT/terminal effect to the entire UI.
 * Respects prefers-reduced-motion for accessibility.
 * 
 * Usage: Place once in App.jsx root level
 */

import { useEffect, useState } from 'react'

export function Scanlines() {
  const [show, setShow] = useState(true)

  useEffect(() => {
    // Check if user prefers reduced motion
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    
    const handleChange = (e) => {
      setShow(!e.matches)
    }
    
    // Set initial state
    setShow(!mediaQuery.matches)
    
    // Listen for changes
    mediaQuery.addEventListener('change', handleChange)
    
    return () => {
      mediaQuery.removeEventListener('change', handleChange)
    }
  }, [])

  if (!show) return null

  return <div className="scanlines" aria-hidden="true" />
}
