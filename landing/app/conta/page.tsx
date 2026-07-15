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
  if (!iso) return "No expiration"
  try {
    return new Date(iso).toLocaleDateString("en-US", {
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
    team: "Team",
    perpetual: "Perpetual",
    trial: "Trial",
  }
  return map[plan] || plan
}

export default function AccountPage() {
  const [email, setEmail] = useState("")
  const [key, setKey] = useState("")
  const [token, setToken] = useState<string | null>(null)
  const [license, setLicense] = useState<PortalLicense | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [booting, setBooting] = useState(true)
  const [pendingDevice, setPendingDevice] = useState<string | null>(null)
  const [checkoutOk, setCheckoutOk] = useState(false)

  const loadMe = useCallback(async (tok: string) => {
    const data = await portalMe(tok)
    setLicense(data.license)
    setToken(tok)
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") return
    const params = new URLSearchParams(window.location.search)
    if (params.get("checkout") === "ok") {
      setCheckoutOk(true)
      window.history.replaceState({}, "", window.location.pathname)
    }
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
      setError(err instanceof Error ? err.message : "Could not sign in.")
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
      setError(err instanceof Error ? err.message : "Failed to deactivate.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />
      <main className="pt-28 pb-20 px-6 md:px-12">
        <div className="max-w-xl mx-auto">
          <p className="text-[11px] tracking-widest uppercase text-black/40 mb-3">Account</p>
          <h1
            className="text-4xl font-light tracking-tight mb-3"
            style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}
          >
            Manage your license
          </h1>
          <p className="text-black/50 text-sm mb-10 leading-relaxed">
            Sign in with the purchase e-mail and the key you received (CDOC-… format).
            No password — the same pair you use to activate the app.
          </p>

          {checkoutOk && (
            <div className="mb-8 rounded-2xl border border-emerald-200 bg-emerald-50 px-6 py-5 text-sm text-emerald-950 leading-relaxed">
              <p className="font-medium mb-1">Payment confirmed</p>
              <p>
                We sent your license key to the <strong>e-mail you used at Stripe
                Checkout</strong>. Check your inbox and the spam folder.
              </p>
              <p className="mt-2 text-emerald-900/80">
                Once you have the key, sign in below (e-mail + key) or activate it in the
                DiffAI app.
              </p>
            </div>
          )}

          {booting ? (
            <p className="text-sm text-black/40">Loading…</p>
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
                  placeholder="you@firm.com"
                />
              </div>
              <div>
                <label htmlFor="key" className="block text-xs tracking-wide text-black/45 mb-2">
                  License key
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
                {loading ? "Signing in…" : "Sign in"}
              </button>
              <p className="text-xs text-black/40 text-center pt-1">
                Don't have a key yet?{" "}
                <Link href="/#pricing" className="underline hover:text-black/70">
                  See pricing
                </Link>
              </p>
            </form>
          ) : (
            <div className="space-y-4">
              <div className="rounded-2xl border border-black/[0.07] bg-white p-8">
                <div className="flex items-start justify-between gap-4 mb-6">
                  <div>
                    <div className="text-xs tracking-widest uppercase text-black/40 mb-1">Plan</div>
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
                    Sign out
                  </button>
                </div>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                  <div>
                    <dt className="text-black/40 text-xs mb-1">E-mail</dt>
                    <dd>{license.email}</dd>
                  </div>
                  <div>
                    <dt className="text-black/40 text-xs mb-1">Key</dt>
                    <dd className="font-mono tracking-wide">{license.key_hint}</dd>
                  </div>
                  <div>
                    <dt className="text-black/40 text-xs mb-1">Valid until</dt>
                    <dd>{formatDate(license.expires_at)}</dd>
                  </div>
                  <div>
                    <dt className="text-black/40 text-xs mb-1">Devices</dt>
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
                  Active devices
                </h2>
                {license.devices.length === 0 ? (
                  <p className="text-sm text-black/45">No device activated yet.</p>
                ) : (
                  <ul className="space-y-3">
                    {license.devices.map((d) => (
                      <li
                        key={d.device}
                        className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-black/[0.06] px-4 py-3"
                      >
                        <div>
                          <div className="text-sm font-medium">{d.device_name || "Device"}</div>
                          <div className="text-xs text-black/40 mt-0.5">
                            Activated {formatDate(d.activated_at)} · last seen {formatDate(d.last_seen)}
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
                              Confirm
                            </button>
                            <button
                              type="button"
                              onClick={() => setPendingDevice(null)}
                              className="text-xs px-3 py-2 rounded-lg border border-black/10 text-black/55"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setPendingDevice(d.device)}
                            className="text-xs px-3 py-2 rounded-lg border border-black/10 text-black/55 hover:border-black/25 hover:text-black"
                          >
                            Deactivate
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <p className="text-xs text-black/40 mt-5 leading-relaxed">
                  Deactivating frees up a slot. Next time the app runs on that machine, it
                  will ask for activation again.
                </p>
              </div>

              {error && (
                <p className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
                  {error}
                </p>
              )}

              <p className="text-xs text-black/40 text-center">
                Need help?{" "}
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
