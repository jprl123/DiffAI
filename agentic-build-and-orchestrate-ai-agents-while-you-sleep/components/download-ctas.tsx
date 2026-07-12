"use client"

import {
  DOWNLOAD_URL_MAC,
  DOWNLOAD_URL_WINDOWS,
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
      href="#baixar"
      className={platformBtn(variant, primary)}
      title="Instalador ainda não publicado — veja a seção Baixar"
    >
      {soonLabel || label}
    </a>
  )
}

/** Botões compactos (hero / nav / CTA escuro). */
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
        readyLabel="Baixar para Mac"
        soonLabel="Baixar para Mac"
        variant={variant}
        primary
      />
      <PlatformLink
        label="Windows"
        url={DOWNLOAD_URL_WINDOWS}
        readyLabel="Baixar para Windows"
        soonLabel="Baixar para Windows"
        variant={variant}
        primary={false}
      />
    </div>
  )
}

/** Seção #baixar — estado real de cada plataforma. */
export function DownloadSection() {
  const macReady = isDownloadReady(DOWNLOAD_URL_MAC)
  const winReady = isDownloadReady(DOWNLOAD_URL_WINDOWS)

  return (
    <section id="baixar" className="py-28 px-6 md:px-12 lg:px-20 scroll-mt-24">
      <div className="max-w-3xl mx-auto">
        <p className="text-[11px] tracking-widest uppercase text-black/40 mb-3">Baixar</p>
        <h2
          className="text-4xl md:text-5xl font-light tracking-tight mb-4"
          style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
        >
          Instale no Mac ou no Windows.
        </h2>
        <p className="text-black/50 mb-10 max-w-xl leading-relaxed">
          O app roda localmente. A internet só entra para ativar a licença e
          gerenciar dispositivos em Conta.
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
                ? "Download do instalador (.dmg)."
                : "Build Mac em preparação. Avise-nos e mandamos o link assim que sair."}
            </p>
            {macReady ? (
              <a
                href={DOWNLOAD_URL_MAC}
                className={`${baseBtn} bg-[#111] text-white hover:bg-black/80`}
              >
                Baixar .dmg
              </a>
            ) : (
              <a
                href={`mailto:${SALES_EMAIL}?subject=Aviso%20quando%20o%20diffAI%20Mac%20estiver%20pronto`}
                className={`${baseBtn} border border-black/15 text-black/70 hover:border-black/30`}
              >
                Avise-me no e-mail
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
                ? "Download do instalador (.exe)."
                : "Build Windows em preparação. Mesmo app, mesma licença — só o instalador muda."}
            </p>
            {winReady ? (
              <a
                href={DOWNLOAD_URL_WINDOWS}
                className={`${baseBtn} bg-[#111] text-white hover:bg-black/80`}
              >
                Baixar .exe
              </a>
            ) : (
              <a
                href={`mailto:${SALES_EMAIL}?subject=Aviso%20quando%20o%20diffAI%20Windows%20estiver%20pronto`}
                className={`${baseBtn} border border-black/15 text-black/70 hover:border-black/30`}
              >
                Avise-me no e-mail
              </a>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
