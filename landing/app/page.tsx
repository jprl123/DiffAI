"use client"

import React, { useCallback, useEffect, useState } from "react"
import { IntroAnimation, HERO_REVEAL_MS } from "@/components/intro-animation"
import { MobileNav } from "@/components/mobile-nav"
import { DownloadButtons, DownloadSection } from "@/components/download-ctas"
import { PixelIcon } from "@/components/pixel-icon"
import { RevealText } from "@/components/reveal-text"
import { StackingChangeCards } from "@/components/stacking-change-cards"
import { ImageSlot } from "@/components/image-slot"
import { BRAND, SALES_EMAIL } from "@/lib/config"
import { HERO_VIDEO, SITE_IMAGES } from "@/lib/images"
import { checkoutUrl } from "@/lib/portal"

// ─── Intersection Observer hook ──────────────────────────────────────────────
function useInView(threshold = 0.15) {
  const ref = React.useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) setInView(true)
      },
      { threshold },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return { ref, inView }
}

// ─── Bento card (template pattern: reveal + hover glow) ──────────────────────
function BentoCard({
  children,
  className = "",
  delay = 0,
}: {
  children: React.ReactNode
  className?: string
  delay?: number
}) {
  const { ref, inView } = useInView(0.1)
  return (
    <div
      ref={ref}
      className={`group relative rounded-2xl border border-black/[0.07] bg-white overflow-hidden transition-all duration-700 hover:border-black/[0.15] hover:bg-[#fafaf8] ${className}`}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translateY(0)" : "translateY(28px)",
        transition: `opacity 0.7s ease ${delay}ms, transform 0.7s ease ${delay}ms, border-color 0.3s ease, background-color 0.3s ease`,
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{
          background:
            "radial-gradient(400px circle at var(--mouse-x, 50%) var(--mouse-y, 50%), rgba(0,0,0,0.03), transparent 60%)",
        }}
      />
      {children}
    </div>
  )
}

// ─── Pill tag ─────────────────────────────────────────────────────────────────
function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] tracking-widest font-sans text-black/40 bg-black/[0.04]">
      {children}
    </span>
  )
}

// ─── Copy ─────────────────────────────────────────────────────────────────────
const PLANS = [
  {
    id: "trial",
    name: "Trial",
    price: "Free",
    period: "14 days",
    sub: "Try everything, no card",
    highlight: false,
    cta: "DOWNLOAD & START",
    href: "#download",
    features: [
      "Every Pro feature",
      "Up to 25 comparisons",
      "Batches of up to 5 pairs",
      "No credit card required",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "R$ 59",
    period: "/mo per user",
    sub: "For daily contract review",
    highlight: true,
    cta: "SUBSCRIBE TO PRO",
    href: checkoutUrl("pro"),
    features: [
      "Unlimited comparisons",
      "Faithful redline PDF + editable DOCX",
      "HTML, Excel and JSON reports",
      "Unlimited batches",
      "2 devices per license",
    ],
  },
  {
    id: "team",
    name: "Team",
    price: "R$ 49",
    period: "/mo per user · min. 5",
    sub: "For legal teams",
    highlight: false,
    cta: "SUBSCRIBE TO TEAM",
    href: checkoutUrl("team"),
    features: [
      "Everything in Pro",
      "5 devices per license",
      "Your firm's brand on the PDFs",
      "Priority support",
    ],
  },
]

const STEPS = [
  {
    n: "01",
    title: "Drop",
    desc: "Drag both versions in — DOCX, PDF or Excel. Batch a whole folder and pairs are matched automatically.",
    delay: 0,
    img: SITE_IMAGES.step1Drop,
    label: "drop files screenshot",
  },
  {
    n: "02",
    title: "Compare",
    desc: "The engine aligns clauses, tables and definitions, separating real changes from dates, versions and formatting noise.",
    delay: 80,
    img: SITE_IMAGES.step2Compare,
    label: "comparison progress screenshot",
  },
  {
    n: "03",
    title: "Review",
    desc: "Read the redline the way you would in Word: insertions underlined, deletions struck through, moves in green.",
    delay: 140,
    img: SITE_IMAGES.step3Review,
    label: "redline review screenshot",
  },
  {
    n: "04",
    title: "Share",
    desc: "Export a faithful PDF, an editable DOCX, or an executive summary the client can read in one page.",
    delay: 200,
    img: SITE_IMAGES.step4Share,
    label: "export options screenshot",
  },
]

const MARQUEE_TOP = [
  "Share Purchase Agreements",
  "NDAs",
  "Cap Tables",
  "Articles of Association",
  "Term Sheets",
  "Credit Agreements",
  "Leases",
  "Privacy Policies",
  "Board Minutes",
  "Employment Contracts",
]

const MARQUEE_BOTTOM = [
  "Side Letters",
  "Convertible Notes",
  "Shareholder Agreements",
  "Service Agreements",
  "License Agreements",
  "Loan Amendments",
  "Corporate Bylaws",
  "Settlement Drafts",
  "Purchase Orders",
  "Engagement Letters",
]

// ─── Main page ────────────────────────────────────────────────────────────────
export default function HomePage() {
  const [heroReady, setHeroReady] = useState(false)
  const [videoReady, setVideoReady] = useState(false)
  const handleIntroDone = useCallback(() => setHeroReady(true), [])

  useEffect(() => {
    const t = setTimeout(() => setVideoReady(true), HERO_REVEAL_MS)
    return () => clearTimeout(t)
  }, [])

  const handleMouse = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const rect = el.getBoundingClientRect()
    el.style.setProperty("--mouse-x", `${e.clientX - rect.left}px`)
    el.style.setProperty("--mouse-y", `${e.clientY - rect.top}px`)
  }

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <IntroAnimation onDone={handleIntroDone} />
      <MobileNav />

      {/* ── HERO ──────────────────────────────────────────────────────────── */}
      <section className="relative h-screen overflow-hidden">
        <video
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 w-full h-full object-cover z-0"
          src={HERO_VIDEO}
          style={{
            transform: videoReady ? "scale(1.05)" : "scale(0.85)",
            transition: "transform 2s cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        />
        {/* Light gradient rising from bottom */}
        <div
          className="absolute inset-x-0 bottom-0 z-10 pointer-events-none"
          style={{
            height: "65%",
            background:
              "linear-gradient(to top, #F5F4F0 0%, #F5F4F0 18%, rgba(245,244,240,0.85) 35%, rgba(245,244,240,0.5) 55%, rgba(245,244,240,0.15) 75%, transparent 100%)",
          }}
        />
        {/* Progressive backdrop blur — template hero polish */}
        <div
          className="absolute inset-x-0 bottom-0 z-10 pointer-events-none"
          style={{
            height: "20%",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            maskImage: "linear-gradient(to top, black 0%, transparent 100%)",
            WebkitMaskImage: "linear-gradient(to top, black 0%, transparent 100%)",
          }}
        />
        <div
          className="absolute inset-x-0 bottom-0 z-10 pointer-events-none"
          style={{
            height: "38%",
            backdropFilter: "blur(6px)",
            WebkitBackdropFilter: "blur(6px)",
            maskImage: "linear-gradient(to top, black 0%, transparent 100%)",
            WebkitMaskImage: "linear-gradient(to top, black 0%, transparent 100%)",
          }}
        />
        <div
          className="absolute inset-x-0 bottom-0 z-10 pointer-events-none"
          style={{
            height: "55%",
            backdropFilter: "blur(2px)",
            WebkitBackdropFilter: "blur(2px)",
            maskImage: "linear-gradient(to top, black 0%, transparent 100%)",
            WebkitMaskImage: "linear-gradient(to top, black 0%, transparent 100%)",
          }}
        />

        <div className="h-20" />

        <div className="absolute inset-x-0 bottom-0 z-30 flex flex-col px-6 md:px-12 pb-12 max-w-3xl">
          <p
            className="text-xs tracking-[0.3em] uppercase text-black/45 mb-4"
            style={{
              fontFamily: '"IBM Plex Sans", sans-serif',
              opacity: heroReady ? 1 : 0,
              transition: "opacity 0.8s ease",
            }}
          >
            {BRAND}
          </p>
          <h1
            className="text-5xl sm:text-6xl md:text-7xl font-light text-[#111] leading-[1.05] tracking-tight mb-6"
            style={{
              fontFamily: '"IBM Plex Sans", sans-serif',
              opacity: heroReady ? 1 : 0,
              filter: heroReady ? "blur(0px)" : "blur(24px)",
              transform: heroReady ? "translateY(0px)" : "translateY(32px)",
              transition:
                "opacity 1s cubic-bezier(0.16,1,0.3,1), filter 1s cubic-bezier(0.16,1,0.3,1), transform 1s cubic-bezier(0.16,1,0.3,1)",
            }}
          >
            Professional
            <br />
            redlines, in
            <br />
            seconds.
          </h1>
          <p
            className="text-base md:text-lg text-black/55 max-w-xl mb-8 leading-relaxed"
            style={{
              fontFamily: '"IBM Plex Sans", sans-serif',
              opacity: heroReady ? 1 : 0,
              transition: "opacity 1s ease 0.15s",
            }}
          >
            Compare versions of DOCX, PDF and Excel files and get a faithful
            redline PDF — processed 100% locally on your Mac or Windows machine.
          </p>
          <div
            style={{
              opacity: heroReady ? 1 : 0,
              transition: "opacity 1s ease 0.25s",
            }}
          >
            <DownloadButtons variant="hero" />
          </div>
        </div>
      </section>

      {/* ── PRODUCT (bento) ───────────────────────────────────────────────── */}
      <section id="product" className="py-32 px-6 md:px-12 lg:px-20 scroll-mt-24">
        <div className="max-w-6xl mx-auto">
          <div className="mb-16">
            <PixelIcon type="platform" size={40} />
            <div className="mt-4">
              <Tag>PRODUCT</Tag>
            </div>
            <RevealText className="mt-5 text-4xl md:text-5xl lg:text-6xl font-light tracking-tight leading-[1.05]">
              {"Built for people who\nreview contracts daily."}
            </RevealText>
          </div>

          <div className="grid grid-cols-12 gap-3" onMouseMove={handleMouse}>
            {/* Big card — product screenshot slot over the arc background */}
            <BentoCard
              className="col-span-12 p-8 min-h-[340px] flex flex-col justify-between relative overflow-hidden"
              delay={0}
            >
              <img
                src={SITE_IMAGES.arc || "/placeholder.svg"}
                alt=""
                aria-hidden="true"
                className="absolute inset-0 w-full h-full object-cover"
                style={{ objectPosition: "center 70%" }}
              />
              <div
                className="absolute inset-0"
                style={{
                  maskImage: "linear-gradient(to bottom, transparent 45%, black 100%)",
                  WebkitMaskImage: "linear-gradient(to bottom, transparent 45%, black 100%)",
                  backdropFilter: "blur(16px)",
                  WebkitBackdropFilter: "blur(16px)",
                }}
              />
              <div
                className="absolute inset-0"
                style={{
                  background:
                    "linear-gradient(to bottom, transparent 35%, rgba(245,244,240,0.3) 50%, rgba(245,244,240,0.75) 65%, rgba(245,244,240,0.95) 80%, rgb(245,244,240) 100%)",
                }}
              />
              <div className="relative z-10 grid md:grid-cols-2 gap-8 items-end h-full">
                <div className="flex flex-col justify-end">
                  <div
                    className="w-10 h-10 rounded-xl border border-black/10 bg-white/60 flex items-center justify-center mb-6"
                    style={{ backdropFilter: "blur(8px)" }}
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="9" y1="13" x2="15" y2="13" />
                      <line x1="9" y1="17" x2="13" y2="17" />
                    </svg>
                  </div>
                  <h3 className="text-xl font-light mb-3">A faithful redline, not a reformatted one</h3>
                  <p className="text-sm text-black/45 leading-relaxed max-w-sm">
                    Deletions struck through, insertions underlined, the original layout
                    preserved — the output you'd expect from Word Compare, without the setup.
                  </p>
                </div>
                <ImageSlot
                  src={SITE_IMAGES.productHero}
                  alt="DiffAI app showing a redline"
                  label="product screenshot — redline view"
                  className="w-full h-48 md:h-56"
                  imgClassName="w-full h-full object-cover object-top rounded-xl border border-black/[0.08] shadow-[0_20px_50px_rgba(0,0,0,0.10)]"
                />
              </div>
            </BentoCard>

            {/* Bottom row */}
            <BentoCard className="col-span-12 md:col-span-4 p-8 min-h-[200px]" delay={120}>
              <div className="w-10 h-10 rounded-xl border border-black/10 flex items-center justify-center mb-5">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </svg>
              </div>
              <h3 className="text-lg font-light mb-2">Signal vs. noise</h3>
              <p className="text-sm text-black/45 leading-relaxed">
                Content changes are separated from dates, version stamps and formatting.
                You review what actually matters.
              </p>
            </BentoCard>

            <BentoCard className="col-span-12 md:col-span-4 p-8 min-h-[200px]" delay={160}>
              <div className="w-10 h-10 rounded-xl border border-black/10 flex items-center justify-center mb-5">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M8 10h8M8 14h5" />
                </svg>
              </div>
              <h3 className="text-lg font-light mb-2">DOCX, PDF & Excel</h3>
              <p className="text-sm text-black/45 leading-relaxed">
                Contracts, policies and cap tables in the same flow. Batch entire folders
                with automatic pairing.
              </p>
            </BentoCard>

            <BentoCard className="col-span-12 md:col-span-4 p-8 min-h-[200px]" delay={200}>
              <div className="w-10 h-10 rounded-xl border border-black/10 flex items-center justify-center mb-5">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </div>
              <h3 className="text-lg font-light mb-2">100% local</h3>
              <p className="text-sm text-black/45 leading-relaxed">
                Documents never leave your computer. Only license activation talks to the
                internet — everything else stays on your machine.
              </p>
            </BentoCard>
          </div>
        </div>
      </section>

      {/* ── CHANGE TYPES (stacking cards) ─────────────────────────────────── */}
      <section id="changes" className="py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06] scroll-mt-24">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-8 mb-16">
            <div>
              <PixelIcon type="agents" size={40} />
              <div className="mt-4">
                <Tag>WHAT GETS MARKED</Tag>
              </div>
              <RevealText className="mt-5 text-4xl md:text-5xl font-light tracking-tight leading-[1.05]">
                {"Every change,\nclassified and counted."}
              </RevealText>
            </div>
            <p className="text-sm text-black/45 leading-relaxed max-w-xs">
              The engine doesn't just diff text — it classifies each change the way a
              reviewer would, and totals them in the Summary of Changes.
            </p>
          </div>

          <StackingChangeCards />
        </div>
      </section>

      {/* ── HOW IT WORKS ──────────────────────────────────────────────────── */}
      <section id="workflow" className="py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06] overflow-hidden scroll-mt-24">
        <div className="max-w-6xl mx-auto">
          <div className="mb-16">
            <PixelIcon type="workflow" size={40} />
            <div className="mt-4">
              <Tag>WORKFLOW</Tag>
            </div>
            <RevealText className="mt-5 text-4xl md:text-5xl font-light tracking-tight leading-[1.05]">
              {"From two versions to a\nclean redline in four steps."}
            </RevealText>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3" onMouseMove={handleMouse}>
            {STEPS.map((step) => (
              <BentoCard key={step.n} className="relative overflow-hidden flex flex-col min-h-[320px]" delay={step.delay}>
                <div className="absolute inset-x-0 top-0 h-56 pointer-events-none p-3">
                  <ImageSlot
                    src={step.img}
                    alt={step.title}
                    label={step.label}
                    className="w-full h-full"
                    imgClassName="w-full h-full object-cover object-top"
                    imgStyle={{
                      maskImage: "linear-gradient(to bottom, black 0%, black 30%, transparent 80%)",
                      WebkitMaskImage: "linear-gradient(to bottom, black 0%, black 30%, transparent 80%)",
                    }}
                  />
                </div>
                <div className="relative z-10 p-7">
                  <span className="font-pixel text-[11px] text-black/20 tracking-widest block">{step.n}</span>
                </div>
                <div className="relative z-10 px-7 pb-7 mt-auto pt-16">
                  <h3 className="text-2xl font-light mb-3">{step.title}</h3>
                  <p className="text-sm text-black/45 leading-relaxed">{step.desc}</p>
                </div>
              </BentoCard>
            ))}
          </div>
        </div>
      </section>

      {/* ── MARQUEE — document types ──────────────────────────────────────── */}
      <section className="py-0 border-t border-black/[0.06] overflow-hidden select-none">
        <div className="flex border-b border-black/[0.06]" style={{ animation: "marqueeLeft 28s linear infinite" }}>
          {[...Array(3)].map((_, rep) => (
            <div key={rep} className="flex shrink-0">
              {MARQUEE_TOP.map((cap) => (
                <div key={cap} className="flex items-center gap-6 px-10 py-5 border-r border-black/[0.06] shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-black/20 shrink-0" />
                  <span className="text-sm text-black/45 whitespace-nowrap tracking-wide">{cap}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
        <div className="flex" style={{ animation: "marqueeRight 22s linear infinite" }}>
          {[...Array(3)].map((_, rep) => (
            <div key={rep} className="flex shrink-0">
              {MARQUEE_BOTTOM.map((cap) => (
                <div key={cap} className="flex items-center gap-6 px-10 py-5 border-r border-black/[0.06] shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-black/12 shrink-0" />
                  <span className="text-sm text-black/30 whitespace-nowrap tracking-wide">{cap}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </section>

      {/* ── PRIVACY ───────────────────────────────────────────────────────── */}
      <section id="privacy" className="py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06] scroll-mt-24">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
              <PixelIcon type="integrations" size={40} />
              <div className="mt-4">
                <Tag>PRIVACY</Tag>
              </div>
              <RevealText className="mt-5 text-4xl md:text-5xl font-light tracking-tight leading-[1.05]">
                {"Your documents never\nleave your computer."}
              </RevealText>
              <p className="mt-6 text-base text-black/40 leading-relaxed max-w-sm">
                Comparison runs entirely on your machine. The only network call is license
                activation — the same endpoint the Account page uses to manage devices.
              </p>
            </div>
            <div className="space-y-4">
              {[
                { label: "Local processing", desc: "No document, clause or metadata is ever uploaded" },
                { label: "Offline after activation", desc: "Compare with the network cable unplugged if you like" },
                { label: "Your outputs, your disk", desc: "Redlines and reports are written to a folder you choose" },
              ].map((item) => (
                <div key={item.label} className="flex gap-4">
                  <div className="w-1 bg-black/10 rounded-full shrink-0" />
                  <div>
                    <h3 className="text-sm font-light mb-1">{item.label}</h3>
                    <p className="text-xs text-black/35">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── PRICING ───────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06] scroll-mt-24">
        {/* Legacy anchor — Stripe CANCEL_URL still points to /#planos */}
        <span id="planos" className="block relative -top-24" aria-hidden="true" />
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16 flex flex-col items-center">
            <PixelIcon type="pricing" size={40} />
            <div className="mt-4">
              <Tag>PRICING</Tag>
            </div>
            <RevealText className="mt-5 text-4xl md:text-5xl font-light tracking-tight leading-[1.05]">
              {"Simple. No surprises."}
            </RevealText>
            <p className="mt-5 text-black/50 max-w-xl text-sm leading-relaxed">
              The trial starts automatically in the app. Subscribing sends your license key
              by e-mail — activate it on Mac or Windows, and manage devices in Account.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3" onMouseMove={handleMouse}>
            {PLANS.map((plan, i) => (
              <BentoCard
                key={plan.id}
                className={`p-8 flex flex-col ${plan.highlight ? "border-black/20 bg-[#F0EEE8]" : ""}`}
                delay={i * 80}
              >
                <div className="mb-8">
                  <div className="font-pixel text-[11px] tracking-widest text-black/40 mb-4">
                    {plan.name.toUpperCase()}
                  </div>
                  <div className="flex items-baseline gap-1 mb-1">
                    <span className="text-4xl font-light">{plan.price}</span>
                    {plan.period && <span className="text-black/40 text-sm">{plan.period}</span>}
                  </div>
                  <p className="text-xs text-black/35 tracking-wide">{plan.sub}</p>
                </div>
                <ul className="space-y-3 flex-1 mb-8">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-center gap-3 text-sm text-black/55">
                      <div className="w-1 h-1 rounded-full bg-black/25 shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <a
                  href={plan.href}
                  className={`w-full py-3 rounded-xl text-sm tracking-widest transition-all duration-200 text-center ${
                    plan.highlight
                      ? "bg-[#111] text-white hover:bg-[#333]"
                      : "border border-black/10 text-black/60 hover:border-black/25 hover:text-black hover:bg-black/[0.04]"
                  }`}
                >
                  {plan.cta}
                </a>
              </BentoCard>
            ))}
          </div>
          <p className="text-center text-sm text-black/40 mt-10">
            Questions?{" "}
            <a href={`mailto:${SALES_EMAIL}`} className="underline hover:text-black/70">
              {SALES_EMAIL}
            </a>
          </p>
        </div>
      </section>

      {/* ── DOWNLOAD ──────────────────────────────────────────────────────── */}
      <DownloadSection />

      {/* ── FINAL CTA (glass panels image) ────────────────────────────────── */}
      <section className="relative py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06] overflow-hidden">
        <img
          src={SITE_IMAGES.ctaFooter || "/placeholder.svg"}
          alt=""
          aria-hidden="true"
          className="absolute bottom-0 left-0 w-full object-cover object-bottom pointer-events-none select-none"
          style={{ opacity: 0.85 }}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            maskImage: "linear-gradient(to top, transparent 0%, black 55%)",
            WebkitMaskImage: "linear-gradient(to top, transparent 0%, black 55%)",
            backdropFilter: "blur(18px)",
            WebkitBackdropFilter: "blur(18px)",
          }}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "linear-gradient(to top, rgb(245,244,240) 0%, rgba(245,244,240,0.92) 18%, rgba(245,244,240,0.55) 35%, transparent 55%)",
          }}
        />
        <div className="relative z-10 max-w-2xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-light tracking-tight leading-[1.05] mb-6">
            Ready to compare
            <br />
            for real.
          </h2>
          <p className="text-sm text-black/45 leading-relaxed mb-10">
            Download {BRAND}, run the trial, and subscribe when you need unlimited
            comparisons.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <DownloadButtons variant="hero" />
            <a
              href="/conta"
              className="inline-flex items-center px-5 py-3 rounded-xl border border-black/15 text-sm text-black/70 hover:border-black/30 hover:text-black transition-colors"
            >
              I already have a license
            </a>
          </div>
        </div>
      </section>

      {/* ── FOOTER ────────────────────────────────────────────────────────── */}
      <footer className="py-10 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
          <span className="font-pixel text-xs tracking-[0.25em] text-black/50">{BRAND}</span>

          <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
            {[
              { label: "Product", href: "#product" },
              { label: "Changes", href: "#changes" },
              { label: "Workflow", href: "#workflow" },
              { label: "Privacy", href: "#privacy" },
              { label: "Pricing", href: "#pricing" },
              { label: "Download", href: "#download" },
            ].map((l) => (
              <a
                key={l.label}
                href={l.href}
                className="text-xs text-black/35 hover:text-black/70 transition-colors tracking-widest"
              >
                {l.label}
              </a>
            ))}
          </div>

          <div className="flex items-center gap-6">
            <a href="/conta" className="text-xs text-black/25 hover:text-black/55 transition-colors tracking-widest">
              Account
            </a>
            <a
              href={`mailto:${SALES_EMAIL}`}
              className="text-xs text-black/25 hover:text-black/55 transition-colors tracking-widest"
            >
              Contact
            </a>
          </div>
        </div>
        <div className="max-w-6xl mx-auto mt-8 pt-6 border-t border-black/[0.04]">
          <span className="text-xs text-black/20">© 2026 {BRAND}. All rights reserved.</span>
        </div>
      </footer>
    </div>
  )
}
