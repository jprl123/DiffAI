// Central image map for the landing page.
//
// Every marketing image lives in `landing/public/images/` and is referenced
// here by slot name. To ship a new image, drop the file in that folder with
// the exact filename below — no code changes needed. While a file is missing,
// <ImageSlot> renders a subtle labeled placeholder instead of a broken image.

export const SITE_IMAGES = {
  /** PRODUCT bento — big card. Suggested: app window showing a redline PDF
   *  side by side with the source DOCX. Landscape, ~1600×900. */
  productHero: "/images/product-hero.png",

  /** HOW IT WORKS — step cards (top-fade like the template). ~800×600 each. */
  step1Drop: "/images/step-1-drop.png",
  step2Compare: "/images/step-2-compare.png",
  step3Review: "/images/step-3-review.png",
  step4Share: "/images/step-4-share.png",

  /** CHANGE TYPES stacking cards — optional; when absent, each card renders
   *  a CSS redline preview instead. ~900×700, right-side composition. */
  changeInsertion: "/images/change-insertion.png",
  changeDeletion: "/images/change-deletion.png",
  changeMove: "/images/change-move.png",
  changeFormatting: "/images/change-formatting.png",

  /** Final CTA background (glass panels). Already shipped with the template. */
  ctaFooter: "/images/footer.png",

  /** PRODUCT bento — big card background arc. Shipped with the template. */
  arc: "/images/arc.png",
} as const

export type SiteImageSlot = keyof typeof SITE_IMAGES

/** Hero background video. Swap for a local file (e.g. /images/hero.mp4)
 *  when the product video is ready. */
export const HERO_VIDEO =
  "https://hebbkx1anhila5yf.public.blob.vercel-storage.com/agentic-hero-9yW3wnTNMfn2U6lsVhTTZSJFEvAoSj.mp4"
