"""Tema visual, constantes e utilitários de animação."""
from __future__ import annotations

from typing import Callable, Optional

# Paleta alinhada à versão web
COLORS = {
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "success": "#16a34a",
    "danger": "#dc2626",
    "warn": "#d97706",
    "muted": "#64748b",
}

# Tuplas de fonte — compatíveis com Tk do macOS (CTkFont exige janela já criada).
FONT_TITLE = ("Helvetica", 22, "bold")
FONT_HEADING = ("Helvetica", 15, "bold")
FONT_BODY = ("Helvetica", 13)
FONT_SMALL = ("Helvetica", 11)
FONT_LOGO = ("Helvetica", 26, "bold")

# Evitar fg_color="transparent" — no Tk do macOS os filhos somem.
PANEL_BG = ("gray90", "gray20")
SURFACE_BG = ("gray95", "gray16")
INNER_BG = ("gray93", "gray18")

POLL_MS = 200
ANIM_STEP_MS = 16
ANIM_DURATION_MS = 280


def ease_out_cubic(t: float) -> float:
    return 1.0 - pow(1.0 - t, 3)


def animate_value(
    widget,
    attr: str,
    start: float,
    end: float,
    duration_ms: int = ANIM_DURATION_MS,
    on_done: Optional[Callable[[], None]] = None,
) -> None:
    """Interpola um atributo numérico de widget com easing."""
    steps = max(1, duration_ms // ANIM_STEP_MS)
    current = [0]

    def tick() -> None:
        current[0] += 1
        t = ease_out_cubic(min(1.0, current[0] / float(steps)))
        value = start + (end - start) * t
        try:
            if attr == "progress":
                widget.set(value)
            else:
                setattr(widget, attr, value)
        except Exception:
            pass
        if current[0] < steps:
            widget.after(ANIM_STEP_MS, tick)
        elif on_done is not None:
            on_done()

    tick()


def animate_progress_bar(bar, target: float, on_done: Optional[Callable[[], None]] = None) -> None:
    """Anima CTkProgressBar até o valor alvo."""
    try:
        current = float(bar.get())
    except Exception:
        current = 0.0
    animate_value(bar, "progress", current, target, on_done=on_done)
