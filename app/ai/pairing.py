"""Pareamento assistido por IA (passo 4 do lote) via OpenRouter.

Quando o pareamento local (nome → similaridade → conteúdo) deixa arquivos
órfãos dos DOIS lados, um LLM barato lê uma amostra curta de cada documento e
sugere quais base↔revisado são a mesma peça (uma sendo revisão da outra).

É OPT-IN e resiliente: só roda quando o usuário liga a opção E há chave do
OpenRouter configurada; qualquer falha (sem chave, rede, JSON inválido) apenas
registra e devolve lista vazia — os órfãos continuam órfãos, o lote nunca cai.

Config (.env na raiz do projeto):
  OPENROUTER_API_KEY      chave do OpenRouter (obrigatória p/ ligar o recurso)
  OPENROUTER_BASE_URL     default https://openrouter.ai/api/v1
  COMPAREDOCS_AI_MODEL    default deepseek/deepseek-v4-flash
  COMPAREDOCS_AI_PAIRING  "0" desliga o recurso mesmo com chave presente
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
_REQUEST_TIMEOUT = 45.0
_SIGNATURE_CHARS = 700          # amostra curta por documento (custo mínimo)
_MAX_FILES_PER_SIDE = 40        # acima disso o prompt fica caro/impreciso

_dotenv_loaded = False


def _load_dotenv_once() -> None:
    """Carrega o .env da raiz do projeto uma única vez (best-effort).

    No app empacotado (PyInstaller) o .env normalmente não existe — tudo bem,
    as variáveis vêm do ambiente."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(root, ".env")
    if os.path.isfile(env_path):
        try:
            load_dotenv(env_path)
        except Exception:
            logger.debug("Falha ao carregar .env para pareamento por IA", exc_info=True)


def get_api_key() -> str:
    _load_dotenv_once()
    return (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("COMPAREDOCS_AI_KEY")
        or ""
    ).strip()


def _model() -> str:
    _load_dotenv_once()
    return (os.environ.get("COMPAREDOCS_AI_MODEL") or _DEFAULT_MODEL).strip()


def _base_url() -> str:
    _load_dotenv_once()
    return (os.environ.get("OPENROUTER_BASE_URL") or _DEFAULT_BASE_URL).strip().rstrip("/")


def ai_pairing_available() -> bool:
    """True se o pareamento por IA está configurado e habilitado."""
    _load_dotenv_once()
    if (os.environ.get("COMPAREDOCS_AI_PAIRING") or "").strip().lower() == "0":
        return False
    return bool(get_api_key())


def _signature(path: str) -> str:
    """Amostra curta e normalizada do conteúdo (título + início do texto)."""
    from app.extract.loader import load_document

    doc = load_document(path)
    parts: List[str] = []
    if getattr(doc, "title", None):
        parts.append(str(doc.title))
    total = 0
    for block in doc.blocks:
        text = block.normalized_text()
        if not text:
            continue
        parts.append(text)
        total += len(text) + 1
        if total >= _SIGNATURE_CHARS:
            break
    return " ".join(parts)[:_SIGNATURE_CHARS]


def _build_prompt(base_sigs: List[Tuple[str, str]], compare_sigs: List[Tuple[str, str]]) -> str:
    lines: List[str] = []
    lines.append("DOCUMENTOS BASE (originais):")
    for idx, (_name, sig) in enumerate(base_sigs):
        lines.append('B%d: "%s"' % (idx, sig.replace('"', "'")))
    lines.append("")
    lines.append("DOCUMENTOS REVISADOS (versões novas):")
    for idx, (_name, sig) in enumerate(compare_sigs):
        lines.append('R%d: "%s"' % (idx, sig.replace('"', "'")))
    return "\n".join(lines)


_SYSTEM_PROMPT = (
    "Você pareia documentos jurídicos: para cada documento BASE, encontre o "
    "documento REVISADO que é a MESMA peça (uma é revisão/versão da outra), "
    "comparando o CONTEÚDO (partes, objeto, tipo de contrato), não o nome do "
    "arquivo. Responda SOMENTE com JSON no formato "
    '{"pairs":[{"base":<indice B>,"compare":<indice R>}]}. '
    "Inclua apenas pares com alta confiança; deixe de fora quem não tiver "
    "correspondente claro. Cada índice aparece no máximo uma vez."
)


def _parse_pairs(content: str, n_base: int, n_compare: int) -> List[Tuple[int, int]]:
    """Extrai pares (base_idx, compare_idx) do texto do modelo, tolerante a
    cercas de código e texto extra."""
    text = content.strip()
    # Remove cercas ```json ... ```
    text = re.sub(r"^```(?:json)?", "", text.strip()).strip()
    text = re.sub(r"```$", "", text.strip()).strip()
    obj = None
    try:
        obj = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
            except Exception:
                obj = None
    if not isinstance(obj, dict):
        return []
    raw = obj.get("pairs")
    if not isinstance(raw, list):
        return []
    out: List[Tuple[int, int]] = []
    used_b: set = set()
    used_c: set = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            b = int(item.get("base"))
            c = int(item.get("compare"))
        except (TypeError, ValueError):
            continue
        if 0 <= b < n_base and 0 <= c < n_compare and b not in used_b and c not in used_c:
            used_b.add(b)
            used_c.add(c)
            out.append((b, c))
    return out


def pair_by_ai(
    base_dir: str,
    base_names: List[str],
    compare_dir: str,
    compare_names: List[str],
) -> List[Tuple[str, str]]:
    """Pareia órfãos usando um LLM do OpenRouter. Devolve lista de
    ``(base_name, compare_name)``. Nunca levanta: em qualquer falha devolve []."""
    if not base_names or not compare_names:
        return []
    if len(base_names) > _MAX_FILES_PER_SIDE or len(compare_names) > _MAX_FILES_PER_SIDE:
        logger.info("Pareamento por IA pulado: arquivos demais (%d x %d).",
                    len(base_names), len(compare_names))
        return []
    api_key = get_api_key()
    if not api_key:
        return []

    try:
        import httpx
    except Exception as exc:
        logger.warning("Pareamento por IA indisponível: httpx ausente (%s)", exc)
        return []

    def _sigs(directory: str, names: List[str]) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        for name in names:
            try:
                sig = _signature(os.path.join(directory, name))
            except Exception as exc:
                logger.warning("Pareamento por IA: não foi possível ler '%s' (%s)", name, exc)
                sig = ""
            out.append((name, sig))
        return out

    base_sigs = _sigs(base_dir, base_names)
    compare_sigs = _sigs(compare_dir, compare_names)

    body = {
        "model": _model(),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(base_sigs, compare_sigs)},
        ],
    }
    headers = {
        "Authorization": "Bearer %s" % api_key,
        "Content-Type": "application/json",
        # Cabeçalhos recomendados pelo OpenRouter (opcionais, p/ atribuição).
        "HTTP-Referer": "https://diffai.app",
        "X-Title": "Compare Docs",
    }
    url = _base_url() + "/chat/completions"
    try:
        resp = httpx.post(url, json=body, headers=headers, timeout=_REQUEST_TIMEOUT)
    except Exception as exc:
        logger.warning("Pareamento por IA: falha de rede (%s)", exc)
        return []
    if resp.status_code != 200:
        logger.warning("Pareamento por IA: OpenRouter HTTP %s — %s",
                       resp.status_code, resp.text[:200])
        return []
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("Pareamento por IA: resposta inesperada (%s)", exc)
        return []

    idx_pairs = _parse_pairs(content, len(base_sigs), len(compare_sigs))
    result = [(base_sigs[b][0], compare_sigs[c][0]) for b, c in idx_pairs]
    for b, c in result:
        logger.info("Pareamento por IA: '%s' <-> '%s' (modelo %s)", b, c, _model())
    return result
