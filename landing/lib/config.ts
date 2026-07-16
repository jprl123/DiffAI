// Configuração central da landing — URLs vêm de variáveis de ambiente públicas
// (ver .env.example). Enquanto o instalador não existir, o botão abre #baixar
// com status "em breve" em vez de um link morto.

export const BRAND = "DiffAI"
export const BRAND_DOMAIN = "diffai.app"

// Sem barra no final — evita //v1/... (404) quando a env vem com /
export const LICENSE_API = (
  process.env.NEXT_PUBLIC_LICENSE_API ?? "http://127.0.0.1:8390"
).replace(/\/+$/, "")

/** URL do .dmg / .zip macOS. Vazio ou "#" = ainda não publicado. */
export const DOWNLOAD_URL_MAC = (
  process.env.NEXT_PUBLIC_DOWNLOAD_URL_MAC ??
  process.env.NEXT_PUBLIC_DOWNLOAD_URL ??
  "https://github.com/jprl123/DiffAI/releases/download/v0.1.4/diffAI-mac.zip"
).trim()

/** URL do ZIP Windows (pasta com .exe). Vazio = ainda não publicado. */
export const DOWNLOAD_URL_WINDOWS = (
  process.env.NEXT_PUBLIC_DOWNLOAD_URL_WINDOWS ??
  "https://github.com/jprl123/DiffAI/releases/download/v0.1.4/diffAI-windows.zip"
).trim()

export const SALES_EMAIL =
  process.env.NEXT_PUBLIC_SALES_EMAIL ?? `vendas@${BRAND_DOMAIN}`

/** Download oficial do LibreOffice (requerido no Mac para PDF redline fiel). */
export const LIBREOFFICE_DOWNLOAD_URL =
  "https://www.libreoffice.org/download/download-libreoffice/"

export function isDownloadReady(url: string) {
  return Boolean(url) && !url.startsWith("#")
}
