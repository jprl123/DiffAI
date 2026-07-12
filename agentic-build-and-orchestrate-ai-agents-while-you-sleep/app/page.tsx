"use client"

import React, { useCallback, useEffect, useState } from "react"
import { IntroAnimation, HERO_REVEAL_MS } from "@/components/intro-animation"
import { MobileNav } from "@/components/mobile-nav"
import { DownloadButtons, DownloadSection } from "@/components/download-ctas"
import { BRAND, SALES_EMAIL } from "@/lib/config"
import { checkoutUrl } from "@/lib/portal"

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

function FadeIn({
  children,
  className = "",
  delay = 0,
}: {
  children: React.ReactNode
  className?: string
  delay?: number
}) {
  const { ref, inView } = useInView(0.12)
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translateY(0)" : "translateY(24px)",
        transition: `opacity 0.7s ease ${delay}ms, transform 0.7s ease ${delay}ms`,
      }}
    >
      {children}
    </div>
  )
}

const FEATURES = [
  {
    title: "Redline fiel",
    body: "PDF e DOCX com exclusões tachadas e inserções sublinhadas — próximo do Word Compare, sem a dor de configurar.",
  },
  {
    title: "Sinal vs. ruído",
    body: "Separa mudança de conteúdo de datas, versões e formatação. Você revisa o que importa.",
  },
  {
    title: "DOCX, PDF e Excel",
    body: "Contratos, políticas e Cap Tables no mesmo fluxo. Lote de pastas com pareamento automático.",
  },
  {
    title: "100% local",
    body: "Documentos não sobem para a nuvem. Só a licença conversa com a internet — o restante fica no seu computador.",
  },
]

const PLANS = [
  {
    id: "trial",
    name: "Avaliação",
    price: "Grátis",
    period: "14 dias",
    highlight: false,
    cta: "Baixar e começar",
    href: "#baixar",
    features: [
      "Todas as funções do Pro",
      "Até 25 comparações",
      "Lote com até 5 pares",
      "Sem cartão de crédito",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "R$ 59",
    period: "/mês por usuário",
    highlight: true,
    cta: "Assinar o Pro",
    href: checkoutUrl("pro"),
    features: [
      "Comparações ilimitadas",
      "PDF redline fiel + DOCX editável",
      "Relatórios HTML, Excel e JSON",
      "Lote ilimitado",
      "2 dispositivos por licença",
    ],
  },
  {
    id: "team",
    name: "Equipe",
    price: "R$ 49",
    period: "/mês por usuário · mín. 5",
    highlight: false,
    cta: "Assinar Equipe",
    href: checkoutUrl("team"),
    features: [
      "Tudo do Pro",
      "5 dispositivos por licença",
      "Marca do escritório nos PDFs",
      "Suporte prioritário",
    ],
  },
]

export default function HomePage() {
  const [heroReady, setHeroReady] = useState(false)
  const [videoReady, setVideoReady] = useState(false)
  const handleIntroDone = useCallback(() => setHeroReady(true), [])

  useEffect(() => {
    const t = setTimeout(() => setVideoReady(true), HERO_REVEAL_MS)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <IntroAnimation onDone={handleIntroDone} />
      <MobileNav />

      <section className="relative h-screen overflow-hidden">
        <video
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 w-full h-full object-cover z-0"
          src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/agentic-hero-9yW3wnTNMfn2U6lsVhTTZSJFEvAoSj.mp4"
          style={{
            transform: videoReady ? "scale(1.05)" : "scale(0.85)",
            transition: "transform 2s cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        />
        <div
          className="absolute inset-x-0 bottom-0 z-10 pointer-events-none"
          style={{
            height: "65%",
            background:
              "linear-gradient(to top, #F5F4F0 0%, #F5F4F0 18%, rgba(245,244,240,0.85) 35%, rgba(245,244,240,0.5) 55%, rgba(245,244,240,0.15) 75%, transparent 100%)",
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
            Redline profissional
            <br />
            de contratos e
            <br />
            documentos.
          </h1>
          <p
            className="text-base md:text-lg text-black/55 max-w-xl mb-8 leading-relaxed"
            style={{
              fontFamily: '"IBM Plex Sans", sans-serif',
              opacity: heroReady ? 1 : 0,
              transition: "opacity 1s ease 0.15s",
            }}
          >
            Compare versões de DOCX, PDF e Excel e gere o PDF redline em segundos —
            com processamento local no Mac ou no Windows.
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

      <section id="produto" className="py-28 px-6 md:px-12 lg:px-20">
        <div className="max-w-6xl mx-auto">
          <FadeIn>
            <p className="text-[11px] tracking-widest uppercase text-black/40 mb-3">Produto</p>
            <h2
              className="text-4xl md:text-5xl font-light tracking-tight leading-[1.1] max-w-2xl mb-16"
              style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
            >
              Feito para quem revisa contratos todos os dias.
            </h2>
          </FadeIn>
          <div className="grid md:grid-cols-2 gap-4">
            {FEATURES.map((f, i) => (
              <FadeIn key={f.title} delay={i * 80}>
                <div className="rounded-2xl border border-black/[0.07] bg-white p-8 h-full hover:border-black/[0.14] transition-colors">
                  <h3
                    className="text-xl font-light mb-3 tracking-tight"
                    style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
                  >
                    {f.title}
                  </h3>
                  <p className="text-sm text-black/55 leading-relaxed">{f.body}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      <section id="privacidade" className="py-24 px-6 md:px-12 lg:px-20 border-y border-black/[0.06]">
        <div className="max-w-3xl mx-auto text-center">
          <FadeIn>
            <p className="text-[11px] tracking-widest uppercase text-black/40 mb-3">Privacidade</p>
            <h2
              className="text-3xl md:text-4xl font-light tracking-tight mb-5"
              style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
            >
              Seus documentos não saem do computador.
            </h2>
            <p className="text-black/55 leading-relaxed">
              A comparação roda 100% local. A conexão com a internet é só para ativar e
              validar a licença — o mesmo servidor que a página Conta usa para gerenciar
              dispositivos.
            </p>
          </FadeIn>
        </div>
      </section>

      <section id="planos" className="py-28 px-6 md:px-12 lg:px-20">
        <div className="max-w-6xl mx-auto">
          <FadeIn>
            <p className="text-[11px] tracking-widest uppercase text-black/40 mb-3">Planos</p>
            <h2
              className="text-4xl md:text-5xl font-light tracking-tight mb-4"
              style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
            >
              Simples. Sem surpresa.
            </h2>
            <p className="text-black/50 mb-14 max-w-xl">
              Avaliação automática no app. Assinatura libera a chave por e-mail — ative no
              Mac ou Windows, ou gerencie dispositivos em Conta.
            </p>
          </FadeIn>
          <div className="grid md:grid-cols-3 gap-4">
            {PLANS.map((plan, i) => (
              <FadeIn key={plan.id} delay={i * 90}>
                <div
                  className={`rounded-2xl border p-8 h-full flex flex-col ${
                    plan.highlight
                      ? "border-[#111] bg-[#111] text-white"
                      : "border-black/[0.07] bg-white"
                  }`}
                >
                  <div className="text-xs tracking-widest uppercase opacity-50 mb-2">{plan.name}</div>
                  <div
                    className="text-4xl font-light tracking-tight mb-1"
                    style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
                  >
                    {plan.price}
                  </div>
                  <div className={`text-sm mb-8 ${plan.highlight ? "text-white/50" : "text-black/45"}`}>
                    {plan.period}
                  </div>
                  <ul className="space-y-2.5 mb-10 flex-1">
                    {plan.features.map((feat) => (
                      <li
                        key={feat}
                        className={`text-sm leading-snug ${plan.highlight ? "text-white/75" : "text-black/60"}`}
                      >
                        {feat}
                      </li>
                    ))}
                  </ul>
                  <a
                    href={plan.href}
                    className={`block text-center text-sm px-4 py-3 rounded-xl tracking-wide transition-colors ${
                      plan.highlight
                        ? "bg-white text-[#111] hover:bg-white/90"
                        : "bg-[#111] text-white hover:bg-black/80"
                    }`}
                  >
                    {plan.cta}
                  </a>
                </div>
              </FadeIn>
            ))}
          </div>
          <p className="text-center text-sm text-black/40 mt-10">
            Dúvidas?{" "}
            <a href={`mailto:${SALES_EMAIL}`} className="underline hover:text-black/70">
              {SALES_EMAIL}
            </a>
          </p>
        </div>
      </section>

      <FadeIn>
        <DownloadSection />
      </FadeIn>

      <section className="py-24 px-6 md:px-12">
        <FadeIn>
          <div className="max-w-4xl mx-auto rounded-3xl bg-[#111] text-white px-8 py-16 text-center">
            <h2
              className="text-3xl md:text-4xl font-light tracking-tight mb-4"
              style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
            >
              Pronto para comparar de verdade.
            </h2>
            <p className="text-white/55 mb-8 max-w-lg mx-auto">
              Baixe o {BRAND}, use a avaliação e assine quando precisar de comparações
              ilimitadas.
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              <DownloadButtons variant="dark" />
              <a
                href="/conta"
                className="inline-flex items-center px-5 py-3 rounded-xl border border-white/20 text-sm text-white/80 hover:border-white/40 hover:text-white transition-colors"
              >
                Já tenho licença
              </a>
            </div>
          </div>
        </FadeIn>
      </section>

      <footer className="px-6 md:px-12 pb-12">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-black/[0.06] pt-8">
          <span className="font-pixel text-[10px] tracking-[0.2em] text-black/40">{BRAND}</span>
          <div className="flex gap-6 text-xs text-black/40">
            <a href="/conta" className="hover:text-black/70">
              Conta
            </a>
            <a href="#baixar" className="hover:text-black/70">
              Baixar
            </a>
            <a href={`mailto:${SALES_EMAIL}`} className="hover:text-black/70">
              Contato
            </a>
            <a href="#planos" className="hover:text-black/70">
              Planos
            </a>
          </div>
          <span className="text-xs text-black/25">© 2026 {BRAND}</span>
        </div>
      </footer>
    </div>
  )
}
