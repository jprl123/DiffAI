"use client"

import { useState } from "react"
import Image from "next/image"
import Link from "next/link"
import { BRAND } from "@/lib/config"

const NAV_LINKS = [
  { label: "Product", href: "/#product" },
  { label: "Changes", href: "/#changes" },
  { label: "Pricing", href: "/#pricing" },
  { label: "Privacy", href: "/#privacy" },
]

const NAV_STYLE = {
  backdropFilter: "blur(16px)",
  WebkitBackdropFilter: "blur(16px)",
  background: "rgba(245,244,240,0.30)",
  boxShadow: "0 8px 32px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.06)",
} as const

export function MobileNav() {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)

  return (
    <div className="fixed top-4 inset-x-0 z-50 flex justify-center px-4 pointer-events-none">
      <div className="pointer-events-auto w-full max-w-3xl">
        <nav
          className="flex items-center justify-between px-5 py-3 rounded-2xl border border-black/[0.06]"
          style={NAV_STYLE}
        >
          <Link href="/" className="flex items-center gap-2.5 text-black/70 hover:text-black transition-colors">
            <Image
              src="/icon.png"
              alt=""
              width={28}
              height={28}
              className="rounded-[7px] shadow-sm"
              priority
            />
            <span className="font-pixel text-xs tracking-[0.2em]">{BRAND}</span>
          </Link>

          <div
            className="hidden md:flex items-center gap-7"
            style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
          >
            {NAV_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                className="text-[11px] text-black/60 hover:text-black transition-colors duration-200 tracking-wide"
              >
                {l.label}
              </a>
            ))}
            <Link
              href="/conta"
              className="text-[11px] text-black/60 hover:text-black transition-colors duration-200 tracking-wide"
            >
              Account
            </Link>
          </div>

          <div className="flex items-center gap-2">
            <a
              href="#download"
              className="text-[11px] px-4 py-2 rounded-xl bg-[#111] text-white hover:bg-black/80 transition-all duration-200 tracking-wide hidden md:block"
              style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
            >
              Download
            </a>

            <button
              onClick={() => setOpen((v) => !v)}
              className="md:hidden flex flex-col justify-center items-center w-8 h-8 gap-[5px] rounded-lg hover:bg-black/[0.04] transition-colors"
              aria-label={open ? "Close menu" : "Open menu"}
            >
              <span
                className="block h-px bg-black/60 transition-all duration-300 origin-center"
                style={{
                  width: "18px",
                  transform: open ? "translateY(6px) rotate(45deg)" : "none",
                }}
              />
              <span
                className="block h-px bg-black/60 transition-all duration-300"
                style={{
                  width: "18px",
                  opacity: open ? 0 : 1,
                  transform: open ? "scaleX(0)" : "none",
                }}
              />
              <span
                className="block h-px bg-black/60 transition-all duration-300 origin-center"
                style={{
                  width: "18px",
                  transform: open ? "translateY(-6px) rotate(-45deg)" : "none",
                }}
              />
            </button>
          </div>
        </nav>

        <div
          className="md:hidden mt-2 overflow-hidden transition-all duration-300 ease-in-out"
          style={{ maxHeight: open ? "400px" : "0px", opacity: open ? 1 : 0 }}
        >
          <div
            className="rounded-2xl border border-black/[0.06] px-2 py-2 flex flex-col"
            style={NAV_STYLE}
          >
            {NAV_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                onClick={close}
                className="px-4 py-3 text-sm text-black/60 hover:text-black hover:bg-black/[0.03] rounded-xl transition-colors tracking-wide"
                style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
              >
                {l.label}
              </a>
            ))}
            <Link
              href="/conta"
              onClick={close}
              className="px-4 py-3 text-sm text-black/60 hover:text-black hover:bg-black/[0.03] rounded-xl transition-colors tracking-wide"
              style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
            >
              Account
            </Link>
            <div className="mt-1 px-2 pb-1">
              <a
                href="#download"
                onClick={close}
                className="block w-full text-center text-[11px] px-4 py-2.5 rounded-xl bg-[#111] text-white tracking-wide"
                style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
              >
                Download for Mac / Windows
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
