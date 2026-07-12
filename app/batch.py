"""Pareamento de arquivos para comparação em lote.

Dado um diretório base e um diretório de comparação, encontra os pares
correspondentes por nome normalizado (caixa, espaços, sufixos de revisão
e marcadores de cópia ignorados). Extensões podem diferir: um ``.docx``
na pasta base pode parear com um ``.pdf`` na pasta revisada.
"""
from __future__ import annotations

import difflib
import logging
import os
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".docx", ".pdf", ".xlsx", ".xlsm")

# Marcador de cópia no final do nome: "Contrato (1)", "Contrato (2) (3)" etc.
_COPY_MARKER_RE = re.compile(r"(\s*\(\d+\))+\s*$")

# Sufixo de revisão no FINAL do nome (aplicado com cautela — ver _normalize_stem):
# " v2", "_rev", "-versão 3", " final", "minuta 2", "draft", "Rev. B" (sem a letra) etc.
_REVISION_SUFFIX_RE = re.compile(
    r"(\s|_|-)*(v|ver|versão|version|rev|revisão|revision|minuta|draft|final)?\.?\s*\d*$",
    re.IGNORECASE,
)

_SEPARATORS_RE = re.compile(r"[\s_\-]+")


def _normalize_stem(stem: str) -> str:
    """Normaliza o stem de um arquivo para pareamento.

    Passos: casefold; colapsa espaços/underscores/hífens; remove marcador de
    cópia "(n)"; remove sufixo de revisão no final — somente se o que sobrar
    tiver pelo menos 3 caracteres (cautela contra nomes curtos como "rev").
    """
    s = stem.casefold()
    s = _SEPARATORS_RE.sub(" ", s).strip()
    s = _COPY_MARKER_RE.sub("", s).strip()
    candidate = _REVISION_SUFFIX_RE.sub("", s, count=1).strip()
    if len(candidate) >= 3:
        s = candidate
    return s


def _list_candidate_files(directory: str) -> List[str]:
    """Lista nomes de arquivos suportados no diretório (sem recursão).

    Ignora arquivos ocultos (".") e temporários do Office ("~$").
    """
    try:
        entries = sorted(os.listdir(directory))
    except OSError as exc:
        raise ValueError(
            "Não foi possível ler o diretório '%s': %s" % (directory, exc)
        )
    files: List[str] = []
    for name in entries:
        if name.startswith(".") or name.startswith("~$"):
            continue
        if not name.lower().endswith(SUPPORTED_EXTENSIONS):
            continue
        full = os.path.join(directory, name)
        if os.path.isfile(full):
            files.append(name)
    return files


def _index_by_stem(names: List[str]) -> Dict[str, List[str]]:
    """Agrupa nomes de arquivo por stem normalizado (preserva ordem)."""
    index: Dict[str, List[str]] = {}
    for name in names:
        stem = os.path.splitext(name)[0]
        key = _normalize_stem(stem)
        if not key:
            key = stem.casefold()
        index.setdefault(key, []).append(name)
    return index


# Pareamento por conteúdo: limites de custo e confiança.
_CONTENT_SIGNATURE_CHARS = 6000   # texto inicial suficiente p/ identificar o doc
_CONTENT_MATCH_THRESHOLD = 0.55   # revisões compartilham a maior parte do texto
_CONTENT_MAX_FILES_PER_SIDE = 50  # acima disso o custo N×M não compensa


def _content_signature(path: str) -> str:
    """Texto normalizado do início do documento (assinatura p/ pareamento)."""
    from app.extract.loader import load_document

    doc = load_document(path)
    parts: List[str] = []
    total = 0
    for block in doc.blocks:
        text = block.normalized_text()
        if not text:
            continue
        parts.append(text)
        total += len(text) + 1
        if total >= _CONTENT_SIGNATURE_CHARS:
            break
    return " ".join(parts)[:_CONTENT_SIGNATURE_CHARS].casefold()


def _pair_by_content(
    base_dir: str,
    base_names: List[str],
    compare_dir: str,
    compare_names: List[str],
) -> List[Tuple[str, str]]:
    """Pareia órfãos pela semelhança do texto (guloso, melhor score primeiro).

    Duas versões do mesmo documento compartilham a maior parte do texto mesmo
    com nomes de arquivo completamente diferentes; documentos distintos não.
    Arquivos ilegíveis são simplesmente ignorados (sem derrubar o lote).
    """
    if (
        len(base_names) > _CONTENT_MAX_FILES_PER_SIDE
        or len(compare_names) > _CONTENT_MAX_FILES_PER_SIDE
    ):
        logger.info(
            "Pareamento por conteúdo pulado: muitos arquivos sem par (%d x %d).",
            len(base_names), len(compare_names),
        )
        return []

    def signatures(directory: str, names: List[str]) -> Dict[str, str]:
        sigs: Dict[str, str] = {}
        for name in names:
            try:
                sig = _content_signature(os.path.join(directory, name))
            except Exception as exc:
                logger.warning(
                    "Pareamento por conteúdo: não foi possível ler '%s' (%s)",
                    name, exc,
                )
                continue
            if sig:
                sigs[name] = sig
        return sigs

    base_sigs = signatures(base_dir, base_names)
    compare_sigs = signatures(compare_dir, compare_names)
    if not base_sigs or not compare_sigs:
        return []

    scored: List[Tuple[float, str, str]] = []
    for base_name, base_sig in base_sigs.items():
        for compare_name, compare_sig in compare_sigs.items():
            matcher = difflib.SequenceMatcher(a=base_sig, b=compare_sig, autojunk=False)
            if matcher.real_quick_ratio() < _CONTENT_MATCH_THRESHOLD:
                continue
            if matcher.quick_ratio() < _CONTENT_MATCH_THRESHOLD:
                continue
            ratio = matcher.ratio()
            if ratio >= _CONTENT_MATCH_THRESHOLD:
                scored.append((ratio, base_name, compare_name))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_base: set = set()
    used_compare: set = set()
    result: List[Tuple[str, str]] = []
    for ratio, base_name, compare_name in scored:
        if base_name in used_base or compare_name in used_compare:
            continue
        used_base.add(base_name)
        used_compare.add(compare_name)
        result.append((base_name, compare_name))
        logger.info(
            "Pareamento por conteúdo: '%s' <-> '%s' (similaridade %.0f%%)",
            base_name, compare_name, ratio * 100,
        )
    return result


def pair_files_detailed(
    base_dir: str, compare_dir: str
) -> Tuple[List[Dict[str, str]], List[str], List[str]]:
    """Como ``pair_files``, mas cada par informa o MÉTODO de pareamento —
    "nome" (stem normalizado igual), "similaridade" (nome parecido) ou
    "conteúdo" (texto dos documentos). Alimenta a prévia do lote na UI."""
    pairs, unmatched_base, unmatched_compare, methods = _pair_files_impl(
        base_dir, compare_dir
    )
    detailed = [
        {
            "base": b,
            "compare": c,
            "base_name": os.path.basename(b),
            "compare_name": os.path.basename(c),
            "method": methods.get((os.path.basename(b), os.path.basename(c)), "nome"),
        }
        for b, c in pairs
    ]
    return detailed, unmatched_base, unmatched_compare


def pair_files(
    base_dir: str, compare_dir: str
) -> Tuple[List[Tuple[str, str]], List[str], List[str]]:
    """Encontra pares (base, comparação) entre dois diretórios.

    Retorna ``(pairs, unmatched_base, unmatched_compare)`` onde:

    - ``pairs``: lista de tuplas ``(caminho_base, caminho_compare)`` com
      caminhos absolutos, ordenada pelo nome do arquivo base;
    - ``unmatched_base`` / ``unmatched_compare``: nomes de arquivos (basename)
      sem correspondente do outro lado.

    Pareamento em 3 passos: stem normalizado igual; similaridade de nome
    (cutoff 0.85); conteúdo dos documentos. Cada arquivo é usado uma vez.
    """
    pairs, unmatched_base, unmatched_compare, _methods = _pair_files_impl(
        base_dir, compare_dir
    )
    return pairs, unmatched_base, unmatched_compare


def _pair_files_impl(
    base_dir: str, compare_dir: str
) -> Tuple[List[Tuple[str, str]], List[str], List[str], Dict[Tuple[str, str], str]]:
    if not base_dir or not os.path.isdir(base_dir):
        raise ValueError("Diretório base inexistente ou inválido: '%s'" % base_dir)
    if not compare_dir or not os.path.isdir(compare_dir):
        raise ValueError(
            "Diretório de comparação inexistente ou inválido: '%s'" % compare_dir
        )

    base_dir = os.path.abspath(base_dir)
    compare_dir = os.path.abspath(compare_dir)

    base_names = _list_candidate_files(base_dir)
    compare_names = _list_candidate_files(compare_dir)

    base_index = _index_by_stem(base_names)
    compare_index = _index_by_stem(compare_names)

    pairs: List[Tuple[str, str]] = []
    methods: Dict[Tuple[str, str], str] = {}
    unmatched_base: List[str] = []
    unmatched_compare_set = set(compare_names)

    # Passo 1: stems normalizados idênticos (um-a-um, em ordem de nome).
    for key in sorted(base_index.keys()):
        base_group = base_index[key]
        compare_group = compare_index.get(key, [])
        n = min(len(base_group), len(compare_group))
        for i in range(n):
            pairs.append((base_group[i], compare_group[i]))
            methods[(base_group[i], compare_group[i])] = "nome"
            unmatched_compare_set.discard(compare_group[i])
        unmatched_base.extend(base_group[n:])

    # Passo 2 (fallback): similaridade de stems normalizados >= 0.85,
    # cada arquivo usado no máximo uma vez.
    remaining_compare = [n for n in compare_names if n in unmatched_compare_set]
    compare_stem_to_names: Dict[str, List[str]] = {}
    for name in remaining_compare:
        stem = _normalize_stem(os.path.splitext(name)[0])
        compare_stem_to_names.setdefault(stem, []).append(name)

    still_unmatched_base: List[str] = []
    for base_name in unmatched_base:
        base_stem = _normalize_stem(os.path.splitext(base_name)[0])
        available_stems = [s for s, lst in compare_stem_to_names.items() if lst]
        matches = difflib.get_close_matches(base_stem, available_stems, n=1, cutoff=0.85)
        if matches:
            chosen_stem = matches[0]
            compare_name = compare_stem_to_names[chosen_stem].pop(0)
            pairs.append((base_name, compare_name))
            methods[(base_name, compare_name)] = "similaridade"
            unmatched_compare_set.discard(compare_name)
            logger.info(
                "Pareamento por similaridade: '%s' <-> '%s'", base_name, compare_name
            )
        else:
            still_unmatched_base.append(base_name)

    unmatched_base = still_unmatched_base
    unmatched_compare = [n for n in compare_names if n in unmatched_compare_set]

    # Passo 3 (conteúdo): arquivos ainda órfãos dos dois lados são pareados
    # pela semelhança do PRÓPRIO TEXTO — dispensa renomear documentos.
    if unmatched_base and unmatched_compare:
        content_pairs = _pair_by_content(
            base_dir, unmatched_base, compare_dir, unmatched_compare
        )
        for base_name, compare_name in content_pairs:
            pairs.append((base_name, compare_name))
            methods[(base_name, compare_name)] = "conteúdo"
            unmatched_base.remove(base_name)
            unmatched_compare.remove(compare_name)

    pairs.sort(key=lambda p: (p[0].casefold(), p[1].casefold()))
    full_pairs = [
        (os.path.join(base_dir, b), os.path.join(compare_dir, c)) for b, c in pairs
    ]
    full_methods = {
        (b, c): methods.get((b, c), "nome") for b, c in pairs
    }

    logger.info(
        "pair_files: %d pares, %d sem par na base, %d sem par na comparação",
        len(full_pairs), len(unmatched_base), len(unmatched_compare),
    )
    return full_pairs, unmatched_base, unmatched_compare, full_methods
