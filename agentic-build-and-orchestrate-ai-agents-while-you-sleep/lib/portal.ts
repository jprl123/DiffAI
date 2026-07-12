// Cliente do portal → servidor de licenças (API pública, sem segredos).
import { LICENSE_API } from "@/lib/config"

export type PortalDevice = {
  device: string
  device_name: string
  activated_at: string
  last_seen: string
}

export type PortalLicense = {
  email: string
  plan: string
  key_hint: string
  expires_at: string | null
  max_devices: number
  status: string
  devices: PortalDevice[]
}

const TOKEN_KEY = "diffai_portal_token"

export function getPortalToken(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(TOKEN_KEY)
}

export function setPortalToken(token: string | null) {
  if (typeof window === "undefined") return
  if (token) window.localStorage.setItem(TOKEN_KEY, token)
  else window.localStorage.removeItem(TOKEN_KEY)
}

async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${LICENSE_API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (data as { detail?: string }).detail
    throw new Error(detail || `Erro HTTP ${res.status}`)
  }
  return data as T
}

export function portalLogin(email: string, key: string) {
  return api<{ token: string; license: PortalLicense }>("/v1/portal/login", {
    method: "POST",
    body: JSON.stringify({ email, key }),
  })
}

export function portalMe(token: string) {
  return api<{ license: PortalLicense }>("/v1/portal/me", {
    headers: { Authorization: `Bearer ${token}` },
  })
}

export function portalDeactivate(token: string, device: string) {
  return api<{ license: PortalLicense }>("/v1/portal/deactivate", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ device }),
  })
}

export function checkoutUrl(plan: "pro" | "team") {
  return `${LICENSE_API}/v1/checkout/${plan}`
}
