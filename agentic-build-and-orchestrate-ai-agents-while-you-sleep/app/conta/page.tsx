"use client"

import { FormEvent, useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { MobileNav } from "@/components/mobile-nav"
import {
  getPortalToken,
  portalDeactivate,
  portalLogin,
  portalMe,
  setPortalToken,
  type PortalLicense,
} from "@/lib/portal"
import { SALES_EMAIL } from "@/lib/config"

function formatDate(iso: string | null) {
  if (!iso) return "Sem expiração"
  try {
    return new Date(iso).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    })
  } catch {
    return iso
  }
}

function planLabel(plan: string) {
  const map: Record<string, string> = {
    pro: "Pro",
    team: "Equipe",
    perpetual: "Perpétua",
    trial: "Avaliação",
  }
  return map[plan] || plan
}

export default function ContaPage() {
  const [email, setEmail] = useState("")
  const [key, setKey] = useState("")
  const [token, setToken] = useState<string | null>(null)
  const [license, setLicense] = useState<PortalLicense | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [booting, setBooting] = useState(true)
  const [pendingDevice, setPendingDevice] = useState<string | null>(null)

  const loadMe = useCallback(async (tok: string) => {
    const data = await portalMe(tok)
    setLicense(data.license)
    setToken(tok)
  }, [])

  useEffect(() => {
    const existing = getPortalToken()
    if (!existing) {
      setBooting(false)
      return
    }
    loadMe(existing)
      .catch(() => {
        setPortalToken(null)
        setToken(null)
        setLicense(null)
      })
      .finally(() => setBooting(false))
  }, [loadMe])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data = await portalLogin(email.trim(), key.trim())
      setPortalToken(data.token)
      setToken(data.token)
      setLicense(data.license)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível entrar.")
    } finally {
      setLoading(false)
    }
  }

  function logout() {
    setPortalToken(null)
    setToken(null)
    setLicense(null)
    setPendingDevice(null)
  }

  async function deactivate(device: string) {
    if (!token) return
    setError(null)
    setLoading(true)
    try {
      const data = await portalDeactivate(token, device)
      setLicense(data.license)
      setPendingDevice(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao desativar.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />
      <main className="pt-28 pb-20 px-6 md:px-12">
        <div className="max-w-xl mx-auto">
          <p className="text-[11px] tracking-widest uppercase text-black/40 mb-3">Conta</p>
          <h1
            className="text-4xl font-light tracking-tight mb-3"
            style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
          >
            Gerenciar licença
          </h1>
          <p className="text-black/50 text-sm mb-10 leading-relaxed">
            Entre com o e-mail da compra e a chave recebida (formato CDOC-…). Sem senha —
            o mesmo par usado para ativar no app.
          </p>

          {booting ? (
            <p className="text-sm text-black/40">Carregando…</p>
          ) : !license ? (
            <form
              onSubmit={onSubmit}
              className="rounded-2xl border border-black/[0.07] bg-white p-8 space-y-5"
            >
              <div>
                <label htmlFor="email" className="block text-xs tracking-wide text-black/45 mb-2">
                  E-mail
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-xl border border-black/10 bg-[#F5F4F0]/50 px-4 py-3 text-sm outline-none focus:border-black/30"
                  placeholder="voce@escritorio.com"
                />
              </div>
              <div>
                <label htmlFor="key" className="block text-xs tracking-wide text-black/45 mb-2">
                  Chave de licença
                </label>
                <input
                  id="key"
                  type="text"
                  required
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  className="w-full rounded-xl border border-black/10 bg-[#F5F4F0]/50 px-4 py-3 text-sm font-mono outline-none focus:border-black/30 tracking-wide"
                  placeholder="CDOC-XXXX-XXXX-XXXX-XXXX"
                />
              </div>
              {error && (
                <p className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
                  {error}
                </p>
              )}
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl bg-[#111] text-white text-sm py-3 hover:bg-black/80 disabled:opacity-50 transition-colors"
              >
                {loading ? "Entrando…" : "Entrar"}
              </button>
              <p className="text-xs text-black/40 text-center pt-1">
                Ainda não tem chave?{" "}
                <Link href="/#planos" className="underline hover:text-black/70">
                  Ver planos
                </Link>
              </p>
            </form>
          ) : (
            <div className="space-y-4">
              <div className="rounded-2xl border border-black/[0.07] bg-white p-8">
                <div className="flex items-start justify-between gap-4 mb-6">
                  <div>
                    <div className="text-xs tracking-widest uppercase text-black/40 mb-1">Plano</div>
                    <div
                      className="text-2xl font-light"
                      style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
                    >
                      {planLabel(license.plan)}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={logout}
                    className="text-xs text-black/45 hover:text-black underline"
                  >
                    Sair
                  </button>
                </div>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                  <div>
                    <dt className="text-black/40 text-xs mb-1">E-mail</dt>
                    <dd>{license.email}</dd>
                  </div>
                  <div>
                    <dt className="text-black/40 text-xs mb-1">Chave</dt>
                    <dd className="font-mono tracking-wide">{license.key_hint}</dd>
                  </div>
                  <div>
                    <dt className="text-black/40 text-xs mb-1">Validade</dt>
                    <dd>{formatDate(license.expires_at)}</dd>
                  </div>
                  <div>
                    <dt className="text-black/40 text-xs mb-1">Dispositivos</dt>
                    <dd>
                      {license.devices.length} / {license.max_devices}
                    </dd>
                  </div>
                </dl>
              </div>

              <div className="rounded-2xl border border-black/[0.07] bg-white p-8">
                <h2
                  className="text-lg font-light mb-4"
                  style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
                >
                  Dispositivos ativos
                </h2>
                {license.devices.length === 0 ? (
                  <p className="text-sm text-black/45">Nenhum dispositivo ativado ainda.</p>
                ) : (
                  <ul className="space-y-3">
                    {license.devices.map((d) => (
                      <li
                        key={d.device}
                        className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-black/[0.06] px-4 py-3"
                      >
                        <div>
                          <div className="text-sm font-medium">{d.device_name || "Dispositivo"}</div>
                          <div className="text-xs text-black/40 mt-0.5">
                            Ativado {formatDate(d.activated_at)} · visto {formatDate(d.last_seen)}
                          </div>
                        </div>
                        {pendingDevice === d.device ? (
                          <div className="flex gap-2">
                            <button
                              type="button"
                              disabled={loading}
                              onClick={() => deactivate(d.device)}
                              className="text-xs px-3 py-2 rounded-lg bg-red-700 text-white hover:bg-red-800 disabled:opacity-50"
                            >
                              Confirmar
                            </button>
                            <button
                              type="button"
                              onClick={() => setPendingDevice(null)}
                              className="text-xs px-3 py-2 rounded-lg border border-black/10 text-black/55"
                            >
                              Cancelar
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setPendingDevice(d.device)}
                            className="text-xs px-3 py-2 rounded-lg border border-black/10 text-black/55 hover:border-black/25 hover:text-black"
                          >
                            Desativar
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <p className="text-xs text-black/40 mt-5 leading-relaxed">
                  Desativar libera uma vaga. No próximo uso, o app pede ativação de novo nesse
                  Mac.
                </p>
              </div>

              {error && (
                <p className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
                  {error}
                </p>
              )}

              <p className="text-xs text-black/40 text-center">
                Precisa de ajuda?{" "}
                <a href={`mailto:${SALES_EMAIL}`} className="underline hover:text-black/70">
                  {SALES_EMAIL}
                </a>
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
