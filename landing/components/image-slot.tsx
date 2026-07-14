"use client"

import { useEffect, useRef, useState } from "react"

/**
 * Image with a graceful placeholder while the asset doesn't exist yet.
 *
 * The landing ships before the marketing images are generated: each slot
 * points to a filename in /public/images (see lib/images.ts). If the file is
 * missing, we render a quiet dashed box with the slot label so the layout —
 * spacing, masks, fades — can be reviewed as if the image were there.
 */
export function ImageSlot({
  src,
  alt,
  label,
  className = "",
  style,
  imgClassName = "",
  imgStyle,
}: {
  src: string
  alt: string
  /** Short label shown inside the placeholder (e.g. "product screenshot"). */
  label?: string
  className?: string
  style?: React.CSSProperties
  imgClassName?: string
  imgStyle?: React.CSSProperties
}) {
  const [missing, setMissing] = useState(false)
  const imgRef = useRef<HTMLImageElement>(null)

  // The error event can fire BEFORE React hydrates and attaches onError
  // (server-rendered img, missing file). Re-check after mount.
  useEffect(() => {
    const img = imgRef.current
    if (img && img.complete && img.naturalWidth === 0) setMissing(true)
  }, [])

  if (missing) {
    return (
      <div
        className={`flex items-center justify-center rounded-xl border border-dashed border-black/15 bg-black/[0.02] ${className}`}
        style={style}
        aria-hidden="true"
      >
        <span className="px-4 text-center text-[10px] tracking-[0.2em] uppercase text-black/25 select-none">
          {label || alt}
        </span>
      </div>
    )
  }

  return (
    <div className={className} style={style}>
      <img
        ref={imgRef}
        src={src || "/placeholder.svg"}
        alt={alt}
        className={imgClassName}
        style={imgStyle}
        onError={() => setMissing(true)}
      />
    </div>
  )
}
