"use client"

import { useRef, useEffect } from "react"
import { SITE } from "@/lib/site"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"

gsap.registerPlugin(ScrollTrigger)

export function ColophonSection() {
  const sectionRef = useRef<HTMLElement>(null)
  const headerRef = useRef<HTMLDivElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const footerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!sectionRef.current) return

    const ctx = gsap.context(() => {
      // Header slide in
      if (headerRef.current) {
        gsap.from(headerRef.current, {
          x: -60,
          opacity: 0,
          duration: 1,
          ease: "power3.out",
          scrollTrigger: {
            trigger: headerRef.current,
            start: "top 85%",
            toggleActions: "play none none reverse",
          },
        })
      }

      // Grid columns fade up with stagger
      if (gridRef.current) {
        const columns = gridRef.current.querySelectorAll(":scope > div")
        gsap.from(columns, {
          y: 40,
          opacity: 0,
          duration: 0.8,
          stagger: 0.1,
          ease: "power3.out",
          scrollTrigger: {
            trigger: gridRef.current,
            start: "top 85%",
            toggleActions: "play none none reverse",
          },
        })
      }

      // Footer fade in
      if (footerRef.current) {
        gsap.from(footerRef.current, {
          y: 20,
          opacity: 0,
          duration: 0.8,
          ease: "power3.out",
          scrollTrigger: {
            trigger: footerRef.current,
            start: "top 95%",
            toggleActions: "play none none reverse",
          },
        })
      }
    }, sectionRef)

    return () => ctx.revert()
  }, [])

  return (
    <section
      ref={sectionRef}
      id="colophon"
      className="relative py-32 pl-6 md:pl-28 pr-6 md:pr-12 border-t border-border/30"
    >
      {/* Section header */}
      <div ref={headerRef} className="mb-16">
        <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-accent">05 / Colophon</span>
        <h2 className="mt-4 font-[var(--font-bebas)] text-5xl md:text-7xl tracking-tight">BUILT WITH</h2>
      </div>

      {/* Multi-column layout */}
      <div ref={gridRef} className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-8 md:gap-12">
        <div className="col-span-1">
          <h4 className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground mb-4">Frontend</h4>
          <ul className="space-y-2">
            <li className="font-mono text-xs text-foreground/80">Next.js 16</li>
            <li className="font-mono text-xs text-foreground/80">React 19</li>
            <li className="font-mono text-xs text-foreground/80">Tailwind CSS 4</li>
            <li className="font-mono text-xs text-foreground/80">GSAP · Lenis</li>
          </ul>
        </div>

        <div className="col-span-1">
          <h4 className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground mb-4">Backend</h4>
          <ul className="space-y-2">
            <li className="font-mono text-xs text-foreground/80">Node.js 20+</li>
            <li className="font-mono text-xs text-foreground/80">viem</li>
            <li className="font-mono text-xs text-foreground/80">Server-Sent Events</li>
          </ul>
        </div>

        <div className="col-span-1">
          <h4 className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground mb-4">AI service</h4>
          <ul className="space-y-2">
            <li className="font-mono text-xs text-foreground/80">Python 3.11+</li>
            <li className="font-mono text-xs text-foreground/80">FastAPI</li>
            <li className="font-mono text-xs text-foreground/80">Pydantic v2</li>
          </ul>
        </div>

        <div className="col-span-1">
          <h4 className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground mb-4">Models</h4>
          <ul className="space-y-2">
            <li className="font-mono text-xs text-foreground/80">Gemini Flash</li>
            <li className="font-mono text-xs text-foreground/80">Claude Haiku 4.5</li>
            <li className="font-mono text-xs text-foreground/80">Claude Sonnet 5.5</li>
          </ul>
        </div>

        <div className="col-span-1">
          <h4 className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground mb-4">Network</h4>
          <ul className="space-y-2">
            <li className="font-mono text-xs text-foreground/80">Base Sepolia</li>
            <li className="font-mono text-xs text-foreground/80">USDC testnet</li>
            <li className="font-mono text-xs text-foreground/80">x402 (next)</li>
          </ul>
        </div>

        <div className="col-span-1">
          <h4 className="font-mono text-[9px] uppercase tracking-[0.3em] text-muted-foreground mb-4">Links</h4>
          <ul className="space-y-2">
            <li>
              <a href={SITE.twitter} target="_blank" rel="noopener noreferrer" className="font-mono text-xs text-foreground/80 hover:text-accent transition-colors duration-200">
                Twitter/X
              </a>
            </li>
            <li>
              <a href={SITE.github} target="_blank" rel="noopener noreferrer" className="font-mono text-xs text-foreground/80 hover:text-accent transition-colors duration-200">
                GitHub
              </a>
            </li>
          </ul>
        </div>
      </div>

      {/* Bottom copyright */}
      <div
        ref={footerRef}
        className="mt-24 pt-8 border-t border-border/20 flex flex-col md:flex-row md:items-center md:justify-between gap-4"
      >
        <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-widest">
          © 2026 Tollgate
        </p>
        <p className="font-mono text-[10px] text-muted-foreground">Free first. Every cent accounted for.</p>
      </div>
    </section>
  )
}
