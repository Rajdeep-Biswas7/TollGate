"use client"

import type React from "react"

import { useEffect, useRef } from "react"
import Lenis from "lenis"
import "lenis/dist/lenis.css"
import { gsap } from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"

gsap.registerPlugin(ScrollTrigger)

declare global {
  interface Window {
    lenis?: Lenis
  }
}

export function SmoothScroll({ children }: { children: React.ReactNode }) {
  const lenisRef = useRef<Lenis | null>(null)

  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: "vertical",
      gestureOrientation: "vertical",
      smoothWheel: true,
      wheelMultiplier: 1.0,
      touchMultiplier: 1.5,
    })

    lenisRef.current = lenis
    window.lenis = lenis

    // Connect Lenis to GSAP ScrollTrigger
    lenis.on("scroll", ScrollTrigger.update)

    const tickerUpdate = (time: number) => {
      lenis.raf(time * 1000)
    }

    gsap.ticker.add(tickerUpdate)
    gsap.ticker.lagSmoothing(0)

    // Handle clicks on internal hash anchor links
    const handleAnchorClick = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement)?.closest?.('a[href^="#"]') as HTMLAnchorElement | null
      if (!anchor) return
      const href = anchor.getAttribute("href")
      if (href && href.startsWith("#") && href.length > 1) {
        const targetEl = document.querySelector(href)
        if (targetEl) {
          e.preventDefault()
          lenis.scrollTo(targetEl as HTMLElement, { offset: -20, duration: 1.2 })
        }
      }
    }

    document.addEventListener("click", handleAnchorClick)

    return () => {
      document.removeEventListener("click", handleAnchorClick)
      gsap.ticker.remove(tickerUpdate)
      lenis.destroy()
      window.lenis = undefined
    }
  }, [])

  return <>{children}</>
}
