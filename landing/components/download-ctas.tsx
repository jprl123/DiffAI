"use client"

import {
  DOWNLOAD_URL_MAC,
  DOWNLOAD_URL_WINDOWS,
  LIBREOFFICE_DOWNLOAD_URL,
  SALES_EMAIL,
  isDownloadReady,
} from "@/lib/config"

type Variant = "hero" | "nav" | "section" | "dark"

const baseBtn =
  "inline-flex items-center justify-center px-5 py-3 rounded-xl text-sm tracking-wide transition-colors"

function platformBtn(variant: Variant, primary: boolean) {
  if (variant === "dark") {
    return primary
      ? `${baseBtn} bg-white text-[#111] hover:bg-white/90`
      : `${baseBtn} border border-white/25 text-white/85 hover:border-white/50 hover:text-white`
  }
  if (variant === "nav") {
    return `${baseBtn} !px-4 !py-2 !text-[11px] bg-[#111] text-white hover:bg-black/80`
  }
  return primary
    ? `${baseBtn} bg-[#111] text-white hover:bg-black/80`
    : `${baseBtn} border border-black/15 text-black/70 hover:border-black/30 hover:text-black`
}

function PlatformLink({
  label,
  url,
  readyLabel,
  soonLabel,
  variant,
  primary,
}: {
  label: string
  url: string
  readyLabel: string
  soonLabel: string
  variant: Variant
  primary: boolean
}) {
  const ready = isDownloadReady(url)
  if (ready) {
    return (
      <a href={url} className={platformBtn(variant, primary)} download>
        {readyLabel}
      </a>
    )
  }
  return (
    <a
      href="#download"
      className={platformBtn(variant, primary)}
      title="Installer not published yet — see the Download section"
    >
      {soonLabel || label}
    </a>
  )
}

/** Compact buttons (hero / nav / dark CTA). */
export function DownloadButtons({
  variant = "hero",
  className = "",
}: {
  variant?: Variant
  className?: string
}) {
  return (
    <div className={`flex flex-wrap gap-3 ${className}`}>
      <PlatformLink
        label="macOS"
        url={DOWNLOAD_URL_MAC}
        readyLabel="Download for Mac"
        soonLabel="Download for Mac"
        variant={variant}
        primary
      />
      <PlatformLink
        label="Windows"
        url={DOWNLOAD_URL_WINDOWS}
        readyLabel="Download for Windows"
        soonLabel="Download for Windows"
        variant={variant}
        primary={false}
      />
    </div>
  )
}

/** #download section — real status per platform. */
export function DownloadSection() {
  const macReady = isDownloadReady(DOWNLOAD_URL_MAC)
  const winReady = isDownloadReady(DOWNLOAD_URL_WINDOWS)

  return (
    <section id="download" className="py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06] scroll-mt-24">
      {/* Legacy anchor — old links may still point to /#baixar */}
      <span id="baixar" className="block relative -top-24" aria-hidden="true" />
      <div className="max-w-3xl mx-auto">
        <p className="text-[11px] tracking-widest uppercase text-black/40 mb-3">Download</p>
        <h2
          className="text-4xl md:text-5xl font-light tracking-tight mb-4"
          style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
        >
          Install on Mac or Windows.
        </h2>
        <p className="text-black/50 mb-10 max-w-xl leading-relaxed">
          The app runs locally. The internet is only used to activate your license and
          manage devices in Account.
        </p>

        <div className="grid sm:grid-cols-2 gap-4">
          <div className="rounded-2xl border border-black/[0.07] bg-white p-8 flex flex-col">
            <div className="text-xs tracking-widest uppercase text-black/40 mb-2">macOS</div>
            <h3
              className="text-xl font-light mb-2"
              style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
            >
              Apple Silicon / Intel
            </h3>
            <p className="text-sm text-black/50 mb-6 flex-1">
              {macReady
                ? "Download the .zip, open it and drag DiffAI.app into Applications. If macOS says the app is damaged, run in Terminal: xattr -cr /Applications/DiffAI.app"
                : "The Mac build is being prepared. Leave your e-mail and we'll send the link as soon as it ships."}
            </p>
            {macReady ? (
              <>
                <a
                  href={DOWNLOAD_URL_MAC}
                  className={`${baseBtn} bg-[#111] text-white hover:bg-black/80`}
                >
                  Download .zip
                </a>
                <div className="mt-5 pt-5 border-t border-black/[0.06]">
                  <p className="text-[12px] text-black/45 leading-relaxed mb-3">
                    <span className="text-black/60 font-medium">Note:</span> For
                    redline PDFs that keep the original DOCX layout, also install{" "}
                    <span className="text-black/70">LibreOffice</span> (free).
                    Without it, the PDF uses a simplified layout; the editable
                    DOCX redline still preserves formatting. The app will prompt
                    you after install.
                  </p>
                  <a
                    href={LIBREOFFICE_DOWNLOAD_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`${baseBtn} !py-2.5 border border-black/15 text-black/70 hover:border-black/30 hover:text-black w-full sm:w-auto`}
                  >
                    Download LibreOffice
                  </a>
                </div>
              </>
            ) : (
              <a
                href={`mailto:${SALES_EMAIL}?subject=Notify%20me%20when%20DiffAI%20for%20Mac%20is%20ready`}
                className={`${baseBtn} border border-black/15 text-black/70 hover:border-black/30`}
              >
                Notify me by e-mail
              </a>
            )}
          </div>

          <div className="rounded-2xl border border-black/[0.07] bg-white p-8 flex flex-col">
            <div className="text-xs tracking-widest uppercase text-black/40 mb-2">Windows</div>
            <h3
              className="text-xl font-light mb-2"
              style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
            >
              Windows 10 / 11
            </h3>
            <p className="text-sm text-black/50 mb-6 flex-1">
              {winReady
                ? "Download the .zip, extract it and run diffAI.exe. Windows 10/11 with WebView2 (usually preinstalled)."
                : "The Windows build is being prepared. Same app, same license — only the installer differs."}
            </p>
            {winReady ? (
              <a
                href={DOWNLOAD_URL_WINDOWS}
                className={`${baseBtn} bg-[#111] text-white hover:bg-black/80`}
              >
                Download .zip
              </a>
            ) : (
              <a
                href={`mailto:${SALES_EMAIL}?subject=Notify%20me%20when%20DiffAI%20for%20Windows%20is%20ready`}
                className={`${baseBtn} border border-black/15 text-black/70 hover:border-black/30`}
              >
                Notify me by e-mail
              </a>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
