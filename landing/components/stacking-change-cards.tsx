"use client"

import { useEffect, useRef, useState } from "react"
import { ImageSlot } from "@/components/image-slot"
import { SITE_IMAGES } from "@/lib/images"

// Stacking ("accordion") cards — one per change type the engine marks in the
// redline. Visuals are CSS-rendered document snippets that match the app's
// palette (see app/output/redline_pdf.py), so no generated images are needed;
// when a matching file exists in /public/images it replaces the CSS preview.

const INSERT_COLOR = "#1a56db"
const DELETE_COLOR = "#c81e1e"
const MOVE_COLOR = "#046c4e"
const FORMAT_BG = "#fdf6b2"

type Snippet = { text: string; op?: "insert" | "delete" | "move" | "format" }[]

const CHANGES: {
  label: string
  title: string
  desc: string
  color: string
  img: string
  snippet: Snippet
}[] = [
  {
    label: "INSERTION",
    title: "New language, underlined in blue",
    desc: "Every word added to the new version is marked inline, exactly where it entered the document — clauses, definitions, schedules, tables.",
    color: INSERT_COLOR,
    img: SITE_IMAGES.changeInsertion,
    snippet: [
      { text: "The Company shall only be required to update its register of members " },
      { text: "once the applicable purchase price has been fully paid and received", op: "insert" },
      { text: "." },
    ],
  },
  {
    label: "DELETION",
    title: "Removed text, struck through in red",
    desc: "Nothing silently disappears. Text removed from the base version stays visible, struck through, so you can judge what the other side took out.",
    color: DELETE_COLOR,
    img: SITE_IMAGES.changeDeletion,
    snippet: [
      { text: "This Agreement is made on the date hereof by and among " },
      { text: "WSGR Draft April 16,", op: "delete" },
      { text: " " },
      { text: "May 07,", op: "insert" },
      { text: " 2025." },
    ],
  },
  {
    label: "MOVE",
    title: "Relocated blocks, tracked in green",
    desc: "When a clause travels to a different section, it isn't a delete plus an insert — it's flagged as moved, with origin and destination.",
    color: MOVE_COLOR,
    img: SITE_IMAGES.changeMove,
    snippet: [
      { text: "⇄ ", op: "move" },
      { text: "9.3 Governing Law. This Agreement shall be governed by the laws of the Cayman Islands.", op: "move" },
    ],
  },
  {
    label: "FORMATTING",
    title: "Style changes, highlighted — never noise",
    desc: "Bold, italics, and casing changes are highlighted separately from content, so a reformatted paragraph never masquerades as a rewrite.",
    color: "#8a6d00",
    img: SITE_IMAGES.changeFormatting,
    snippet: [
      { text: "Each Investor severally, and " },
      { text: "not jointly", op: "format" },
      { text: ", agrees to purchase the Shares at the applicable Closing." },
    ],
  },
]

const STICKY_TOP = 80
const STICKY_STEP = 16
const SCALE_STEP = 0.04
const OFFSET_STEP = 8

function Tag({ children, color }: { children: React.ReactNode; color?: string }) {
  return (
    <span
      className="inline-flex items-center px-3 py-1 rounded-full text-[11px] tracking-widest font-sans bg-black/[0.04]"
      style={{ color: color || "rgba(0,0,0,0.4)" }}
    >
      {children}
    </span>
  )
}

function RedlinePreview({ snippet }: { snippet: Snippet }) {
  return (
    <div className="h-full w-full flex items-center px-8 py-10">
      <div className="w-full rounded-xl border border-black/[0.08] bg-white shadow-[0_16px_40px_rgba(0,0,0,0.06)] p-6">
        {/* Fake document chrome */}
        <div className="flex items-center gap-1.5 mb-4">
          <span className="w-2 h-2 rounded-full bg-black/10" />
          <span className="w-2 h-2 rounded-full bg-black/10" />
          <span className="w-2 h-2 rounded-full bg-black/10" />
        </div>
        <p className="font-serif text-[13px] leading-[1.9] text-black/75">
          {snippet.map((frag, i) => {
            if (frag.op === "insert")
              return (
                <span key={i} style={{ color: INSERT_COLOR, textDecoration: "underline" }}>
                  {frag.text}
                </span>
              )
            if (frag.op === "delete")
              return (
                <span key={i} style={{ color: DELETE_COLOR, textDecoration: "line-through" }}>
                  {frag.text}
                </span>
              )
            if (frag.op === "move")
              return (
                <span key={i} style={{ color: MOVE_COLOR }}>
                  {frag.text}
                </span>
              )
            if (frag.op === "format")
              return (
                <span key={i} style={{ background: FORMAT_BG, fontWeight: 600 }}>
                  {frag.text}
                </span>
              )
            return <span key={i}>{frag.text}</span>
          })}
        </p>
        <div className="mt-4 h-px bg-black/[0.05]" />
        <div className="mt-3 space-y-2">
          <div className="h-1.5 rounded bg-black/[0.05] w-full" />
          <div className="h-1.5 rounded bg-black/[0.05] w-4/5" />
          <div className="h-1.5 rounded bg-black/[0.05] w-2/3" />
        </div>
      </div>
    </div>
  )
}

export function StackingChangeCards() {
  const cardRefs = useRef<(HTMLDivElement | null)[]>([])
  const [depth, setDepth] = useState<number[]>(CHANGES.map(() => 0))
  const [imgOk, setImgOk] = useState<boolean[]>(CHANGES.map(() => true))

  useEffect(() => {
    // Probe each optional image once; fall back to the CSS preview if absent.
    CHANGES.forEach((c, i) => {
      const probe = new Image()
      probe.onload = () => setImgOk((prev) => prev.map((v, j) => (j === i ? true : v)))
      probe.onerror = () => setImgOk((prev) => prev.map((v, j) => (j === i ? false : v)))
      probe.src = c.img
    })
  }, [])

  useEffect(() => {
    function onScroll() {
      const nextDepth = CHANGES.map((_, i) => {
        let count = 0
        for (let j = i + 1; j < CHANGES.length; j++) {
          const el = cardRefs.current[j]
          if (!el) continue
          const rect = el.getBoundingClientRect()
          const stickyTopJ = STICKY_TOP + j * STICKY_STEP
          if (rect.top <= stickyTopJ + 2) count++
        }
        return count
      })
      setDepth(nextDepth)
    }

    window.addEventListener("scroll", onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  return (
    <div className="flex flex-col" style={{ perspective: "1400px", perspectiveOrigin: "50% 0%" }}>
      {CHANGES.map((change, i) => {
        const d = depth[i]
        const scale = 1 - d * SCALE_STEP
        const translateY = d * OFFSET_STEP
        const useImage = imgOk[i]

        return (
          <div
            key={change.label}
            ref={(el) => { cardRefs.current[i] = el }}
            className="sticky mb-4"
            style={{ top: `${STICKY_TOP + i * STICKY_STEP}px`, zIndex: 10 + i }}
          >
            <div
              style={{
                transform: `scale(${scale}) translateY(${translateY}px)`,
                transformOrigin: "top center",
                transition: "transform 0.3s cubic-bezier(0.16,1,0.3,1)",
                willChange: "transform",
              }}
            >
              <div className="group relative bg-[#faf9f7] rounded-2xl border border-black/[0.07] overflow-hidden">
                {/* ── MOBILE: visual on top, fades toward the text ── */}
                <div className="relative w-full h-52 pointer-events-none md:hidden">
                  {useImage ? (
                    <ImageSlot
                      src={change.img}
                      alt={change.label}
                      className="absolute inset-0"
                      imgClassName="w-full h-full object-cover object-center"
                      imgStyle={{
                        maskImage: "linear-gradient(to bottom, black 0%, black 35%, transparent 85%)",
                        WebkitMaskImage: "linear-gradient(to bottom, black 0%, black 35%, transparent 85%)",
                      }}
                    />
                  ) : (
                    <div className="absolute inset-0 scale-90 origin-top">
                      <RedlinePreview snippet={change.snippet} />
                    </div>
                  )}
                </div>

                {/* ── DESKTOP: visual on the right, fading out to the left ── */}
                <div className="hidden md:block absolute inset-y-0 right-0 w-1/2 pointer-events-none">
                  {useImage ? (
                    <ImageSlot
                      src={change.img}
                      alt={change.label}
                      className="w-full h-full"
                      imgClassName="w-full h-full object-cover object-center"
                    />
                  ) : (
                    <RedlinePreview snippet={change.snippet} />
                  )}
                  <div
                    className="absolute inset-0"
                    style={{ background: "linear-gradient(to right, #faf9f7 0%, transparent 55%)" }}
                  />
                </div>

                {/* Text content */}
                <div className="relative z-10 p-8">
                  <div className="md:max-w-[55%]">
                    <div className="flex items-center gap-3 mb-6">
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ background: change.color }}
                      />
                      <Tag color={change.color}>{change.label}</Tag>
                    </div>
                    <h3 className="text-xl font-light mb-3">{change.title}</h3>
                    <p className="text-sm text-black/45 leading-relaxed mb-4">{change.desc}</p>
                  </div>
                  <div className="md:max-w-[55%] pt-6 border-t border-black/[0.06] text-[11px] tracking-widest text-black/30 uppercase">
                    Marked inline · counted in the summary
                  </div>
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
