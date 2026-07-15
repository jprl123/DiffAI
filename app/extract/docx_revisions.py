"""Aceite de marcas de revisão (track changes) em DOCX — pré-compare.

Documento que chega com revisões PENDENTES quebra a comparação em dois
pontos: o extrator não enxerga texto dentro de ``w:ins`` (python-docx só lê
runs filhos diretos do parágrafo), e o redline in-place herdaria as marcas
antigas misturadas às nossas. Por isso, antes de comparar, o pipeline aceita
todas as revisões — sempre em uma CÓPIA temporária; o arquivo do usuário
nunca é modificado (ver app/jobs.py).

Opera no nível do zip/XML (lxml, que já vem com python-docx), cobrindo
document.xml, headers, footers, footnotes e endnotes. Semântica de "aceitar
tudo" do Word:

  - ``w:ins`` / ``w:moveTo``       → desembrulha (conteúdo vira definitivo)
  - ``w:del`` / ``w:moveFrom``     → remove (com o w:delText dentro)
  - marca de parágrafo deletada    → parágrafo funde com o SEGUINTE
    (``w:pPr/w:rPr/w:del``)
  - linha de tabela deletada       → remove a linha (``w:trPr/w:del``)
  - registros de mudança           → remove (pPrChange, rPrChange,
    sectPrChange, tblPrChange, tblGridChange, tcPrChange, cellIns/cellDel,
    numberingChange, move*RangeStart/End)
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import zipfile
from typing import List

from lxml import etree

logger = logging.getLogger(__name__)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Partes do pacote que podem conter revisões.
_PART_RE = re.compile(
    r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$"
)

# Presença de qualquer um destes marca o documento como "com revisões".
# (b'<w:ins ' com espaço — não confundir com <w:insideH> de borda de tabela.)
_REVISION_MARKERS = (
    b"<w:ins ",
    b"<w:del ",
    b"<w:delText",
    b"<w:moveFrom",
    b"<w:moveTo",
    b"<w:pPrChange",
    b"<w:rPrChange",
    b"<w:sectPrChange",
    b"<w:tblPrChange",
    b"<w:tcPrChange",
    b"<w:trPrChange",
    b"<w:cellIns",
    b"<w:cellDel",
    b"<w:numberingChange",
)

# Registros de mudança e marcadores auxiliares removidos por inteiro.
_RECORD_TAGS = (
    _W + "pPrChange", _W + "rPrChange", _W + "sectPrChange",
    _W + "tblPrChange", _W + "tblGridChange", _W + "tcPrChange",
    _W + "trPrChange", _W + "cellIns", _W + "cellDel", _W + "cellMerge",
    _W + "numberingChange",
    _W + "moveFromRangeStart", _W + "moveFromRangeEnd",
    _W + "moveToRangeStart", _W + "moveToRangeEnd",
)


def has_tracked_revisions(docx_path: str) -> bool:
    """True se alguma parte relevante do DOCX contém marcas de revisão."""
    try:
        with zipfile.ZipFile(docx_path) as zf:
            for name in zf.namelist():
                if not _PART_RE.match(name):
                    continue
                data = zf.read(name)
                if any(marker in data for marker in _REVISION_MARKERS):
                    return True
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        logger.warning(
            "Não foi possível inspecionar revisões de '%s': %s", docx_path, exc
        )
    return False


def _unwrap(element: etree._Element) -> None:
    """Substitui o elemento pelos próprios filhos, na mesma posição."""
    parent = element.getparent()
    if parent is None:
        return
    index = parent.index(element)
    for child in reversed(list(element)):
        parent.insert(index, child)
    parent.remove(element)


def _merge_deleted_paragraph_marks(root: etree._Element) -> None:
    """Marca de parágrafo deletada = o parágrafo funde com o seguinte.

    Processa em ordem de documento: o conteúdo do parágrafo é PREPOSTO ao
    próximo ``w:p`` irmão (a formatação do parágrafo resultante é a do
    seguinte, como no Word). Cadeias (várias marcas seguidas) resolvem
    naturalmente. Sem próximo parágrafo irmão, só a marca é removida.
    """
    for p in list(root.iter(_W + "p")):
        ppr = p.find(_W + "pPr")
        if ppr is None:
            continue
        rpr = ppr.find(_W + "rPr")
        if rpr is None or rpr.find(_W + "del") is None:
            continue
        rpr.remove(rpr.find(_W + "del"))
        nxt = p.getnext()
        if nxt is None or nxt.tag != _W + "p":
            continue
        content = [child for child in list(p) if child.tag != _W + "pPr"]
        next_ppr = nxt.find(_W + "pPr")
        insert_at = 1 if next_ppr is not None else 0
        for child in reversed(content):
            nxt.insert(insert_at, child)
        parent = p.getparent()
        if parent is not None:
            parent.remove(p)


def _accept_in_tree(root: etree._Element) -> None:
    # 1. Marcas de parágrafo deletadas (usa w:pPr/w:rPr/w:del — antes de
    #    remover os w:del genéricos).
    _merge_deleted_paragraph_marks(root)

    # 2. Linhas de tabela deletadas somem por inteiro.
    for tr in list(root.iter(_W + "tr")):
        trpr = tr.find(_W + "trPr")
        if trpr is not None and trpr.find(_W + "del") is not None:
            parent = tr.getparent()
            if parent is not None:
                parent.remove(tr)

    # 3. Conteúdo deletado/movido-de sai (leva o w:delText junto).
    for tag in (_W + "del", _W + "moveFrom"):
        for element in list(root.iter(tag)):
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)

    # 4. Conteúdo inserido/movido-para vira definitivo (desembrulha).
    for tag in (_W + "ins", _W + "moveTo"):
        for element in list(root.iter(tag)):
            _unwrap(element)

    # 5. Registros de mudança e marcadores auxiliares.
    for tag in _RECORD_TAGS:
        for element in list(root.iter(tag)):
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)


def accept_all_revisions(docx_path: str) -> None:
    """Aceita todas as revisões DO PRÓPRIO arquivo (use sobre uma cópia)."""
    with zipfile.ZipFile(docx_path) as zf:
        infos = zf.infolist()
        contents = {info.filename: zf.read(info.filename) for info in infos}

    changed: List[str] = []
    for name, data in contents.items():
        if not _PART_RE.match(name):
            continue
        if not any(marker in data for marker in _REVISION_MARKERS):
            continue
        root = etree.fromstring(data)
        _accept_in_tree(root)
        contents[name] = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=True
        )
        changed.append(name)

    if not changed:
        return

    tmp_path = docx_path + ".accepting"
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for info in infos:
            zf.writestr(info.filename, contents[info.filename])
    shutil.move(tmp_path, docx_path)
    logger.info(
        "Revisões aceitas em %s (partes: %s)",
        os.path.basename(docx_path), ", ".join(changed),
    )
