"""Geração de insights em linguagem de negócio — 100% local (sem nuvem).

Analisa o ComparisonResult e produz resumo executivo, destaques, alertas de
risco e recomendações. Heurísticas baseadas em palavras-chave jurídicas/corporativas.
Opcionalmente enriquecível com IA generativa via COMPAREDOCS_AI_KEY (futuro).
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from app.models import NOISE_CATEGORIES, Category, Change, ComparisonResult

_RISK_KEYWORDS = [
    (r"\bmulta\b", "multa"),
    (r"\bpenalidade\b", "penalidade"),
    (r"\bprazo\b", "prazo"),
    (r"\bpagamento\b", "pagamento"),
    (r"\bforo\b", "foro"),
    (r"\brescis", "rescisão"),
    (r"\bconfidencial", "confidencialidade"),
    (r"\bindeniz", "indenização"),
    (r"\bvalor\b", "valor financeiro"),
    (r"R\$\s*[\d\.,]+", "valor monetário"),
    (r"\b\d+\s*%", "percentual"),
    (r"\bvigência\b", "vigência"),
    (r"\bresponsabil", "responsabilidade"),
]

_NOISE_HINT = (
    "As alterações rotineiras (versão, data, numeração) foram separadas do conteúdo "
    "substantivo — você pode ignorá-las na revisão rápida."
)


def _text_blob(change: Change) -> str:
    blob = "%s %s %s" % (
        change.summary or "",
        change.old_text or "",
        change.new_text or "",
    )
    return blob.lower()


def _is_substantive(change: Change) -> bool:
    if change.category in NOISE_CATEGORIES:
        return False
    if change.category == Category.FORMATTING:
        return False
    return change.category in (
        Category.CONTENT,
        Category.TABLE,
        Category.IMAGE,
    )


def _detect_risk(change: Change) -> Optional[str]:
    blob = _text_blob(change)
    for pattern, label in _RISK_KEYWORDS:
        if re.search(pattern, blob, re.IGNORECASE):
            return label
    return None


def _business_line(change: Change) -> str:
    """Uma frase legível sobre a mudança."""
    section = ""
    if change.section_path:
        section = " em «%s»" % " › ".join(change.section_path[-2:])
    summary = change.summary or "Alteração detectada"
    old_t = (change.old_text or "").strip()
    new_t = (change.new_text or "").strip()
    if old_t and new_t and len(old_t) < 120 and len(new_t) < 120:
        return "%s%s: «%s» → «%s»" % (summary, section, old_t[:80], new_t[:80])
    if new_t and not old_t:
        return "%s%s — texto inserido." % (summary, section)
    if old_t and not new_t:
        return "%s%s — trecho removido." % (summary, section)
    return "%s%s." % (summary, section)


def generate_insights(result: ComparisonResult) -> Dict[str, Any]:
    """Gera pacote de insights para a UI e exportação."""
    stats = result.stats
    changes = result.changes or []
    substantive = [c for c in changes if _is_substantive(c)]
    noise_count = stats.noise_changes
    content_count = stats.content_changes

    highlights: List[str] = []
    for ch in substantive[:6]:
        line = _business_line(ch)
        if line not in highlights:
            highlights.append(line)

    risks: List[Dict[str, str]] = []
    seen_risk = set()
    for ch in substantive:
        risk_type = _detect_risk(ch)
        if risk_type and risk_type not in seen_risk:
            seen_risk.add(risk_type)
            risks.append({
                "type": risk_type,
                "message": _business_line(ch),
                "severity": "high" if risk_type in ("multa", "foro", "prazo", "pagamento") else "medium",
            })
        if len(risks) >= 5:
            break

    recommendations: List[str] = []
    if content_count == 0 and stats.total_changes > 0:
        recommendations.append(
            "Nenhuma mudança substantiva de conteúdo — revise apenas formatação e ruído rotineiro."
        )
    elif content_count > 0:
        recommendations.append(
            "Priorize a revisão das %d mudança(s) de conteúdo antes de aprovar a versão revisada."
            % content_count
        )
    if noise_count > 0:
        recommendations.append(_NOISE_HINT)
    if stats.moves > 0:
        recommendations.append(
            "%d cláusula(s) ou bloco(s) foram movidos de posição — verifique a ordem no documento final."
            % stats.moves
        )
    if stats.table_changes > 0:
        recommendations.append("Há alterações em tabelas — confira valores e linhas na planilha Excel.")

    base_name = os.path.basename(result.base_path or "base")
    compare_name = os.path.basename(result.compare_path or "revisado")

    if content_count == 0:
        executive = (
            "Comparação entre «%s» e «%s»: %d alteração(ões) no total, "
            "sem mudanças substantivas de conteúdo."
            % (base_name, compare_name, stats.total_changes)
        )
    else:
        executive = (
            "Comparação entre «%s» e «%s»: %d mudança(s) de conteúdo exigem atenção "
            "(%d rotineiras, %d de formatação). Tempo de processamento: %.1fs."
            % (
                base_name,
                compare_name,
                content_count,
                noise_count,
                stats.formatting_changes,
                result.duration_seconds or 0,
            )
        )

    ai_enhanced = False
    ai_key = os.environ.get("COMPAREDOCS_AI_KEY", "").strip()
    if ai_key:
        # Hook para IA generativa futura — não envia dados sem chave explícita.
        ai_enhanced = False  # placeholder até integração opt-in

    return {
        "executive_summary": executive,
        "highlights": highlights,
        "risks": risks,
        "recommendations": recommendations,
        "stats": {
            "total": stats.total_changes,
            "content": content_count,
            "noise": noise_count,
            "formatting": stats.formatting_changes,
            "moves": stats.moves,
            "tables": stats.table_changes,
        },
        "mode": "ai_enhanced" if ai_enhanced else "local",
        "mode_label": "Análise IA (local)" if not ai_enhanced else "Análise IA (generativa)",
        "privacy": "Nenhum dado foi enviado à nuvem.",
    }
