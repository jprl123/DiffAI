"""Alinhamento de blocos em três passes (exatos, similares, movidos)."""
from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass
from typing import List, Optional

from app.engine.worddiff import runs_have_formatting_diff
from app.models import Block, ChangeType

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.55
MOVE_THRESHOLD = 0.85


@dataclass
class AlignedBlock:
    base_index: Optional[int]
    compare_index: Optional[int]
    change_type: ChangeType


def _text_ratio(a: Block, b: Block) -> float:
    return difflib.SequenceMatcher(
        None, a.normalized_text(), b.normalized_text(), autojunk=False
    ).ratio()


def align_blocks(base_blocks: List[Block], compare_blocks: List[Block]) -> List[AlignedBlock]:
    """Alinha blocos base e revisado; retorna lista em ordem de renderização."""
    n = len(base_blocks)
    m = len(compare_blocks)
    if n == 0 and m == 0:
        return []

    base_status: List[Optional[ChangeType]] = [None] * n
    compare_status: List[Optional[ChangeType]] = [None] * m
    base_pair: List[int] = [-1] * n
    compare_pair: List[int] = [-1] * m

    # Passo 1: casamento exato por content_hash (LCS).
    base_hashes = [b.content_hash() for b in base_blocks]
    compare_hashes = [b.content_hash() for b in compare_blocks]
    matcher = difflib.SequenceMatcher(None, base_hashes, compare_hashes, autojunk=False)
    for bi, bj, size in matcher.get_matching_blocks():
        for offset in range(size):
            i = bi + offset
            j = bj + offset
            base_status[i] = ChangeType.EQUAL
            compare_status[j] = ChangeType.EQUAL
            base_pair[i] = j
            compare_pair[j] = i

    # Pós-pass 1: mesmo texto, formatação diferente → MODIFY.
    for bi in range(n):
        if base_status[bi] != ChangeType.EQUAL:
            continue
        cj = base_pair[bi]
        if cj < 0:
            continue
        if runs_have_formatting_diff(base_blocks[bi].runs, compare_blocks[cj].runs):
            base_status[bi] = ChangeType.MODIFY
            compare_status[cj] = ChangeType.MODIFY

    # Passo 2: similaridade DENTRO de cada vão entre âncoras do passo 1.
    # Confinar ao vão é o que garante que o passo 2 nunca cria pareamento
    # cruzado: parear através de vãos (candidato a movimentação) é papel
    # exclusivo do passo 3. (Um passo 2 global e ganancioso pareava a
    # cláusula movida cedo demais e travava o resto do documento.)
    anchors = sorted(
        (bi, base_pair[bi]) for bi in range(n) if base_status[bi] is not None
    )
    gap_bounds = []
    prev_bi, prev_cj = -1, -1
    for a_bi, a_cj in anchors + [(n, m)]:
        gap_bounds.append(((prev_bi + 1, a_bi), (prev_cj + 1, a_cj)))
        prev_bi, prev_cj = a_bi, a_cj

    # Órfãos com GÊMEO exato (mesmo content_hash) do outro lado são
    # relocações intactas — como o passo 1 (LCS) já casou todos os gêmeos em
    # ordem, um gêmeo restante está fora de ordem = candidato a movimentação.
    # Reservamos para o passo 3: o passo 2 (similaridade) NÃO pode roubá-los
    # parando-os num MODIFY com bloco parecido porém diferente (era o que
    # casava o título de uma cláusula MOVIDA com o de outra EXCLUÍDA, deixando
    # o título fora do movimento e inflando exclusão/inserção).
    base_orphan_hashes = {
        base_hashes[bi] for bi in range(n) if base_status[bi] is None
    }
    compare_orphan_hashes = {
        compare_hashes[cj] for cj in range(m) if compare_status[cj] is None
    }

    for (b_lo, b_hi), (c_lo, c_hi) in gap_bounds:
        base_orphans = [
            bi for bi in range(b_lo, b_hi) if base_status[bi] is None
        ]
        compare_orphans = [
            cj for cj in range(c_lo, c_hi) if compare_status[cj] is None
        ]
        if not base_orphans or not compare_orphans:
            continue
        scored = []
        for bi in base_orphans:
            if base_hashes[bi] in compare_orphan_hashes:
                continue  # relocação intacta: reservada ao passo 3 (movimento)
            for cj in compare_orphans:
                if compare_hashes[cj] in base_orphan_hashes:
                    continue
                ratio = _text_ratio(base_blocks[bi], compare_blocks[cj])
                if ratio >= SIMILARITY_THRESHOLD:
                    scored.append((ratio, bi, cj))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        accepted: List[tuple] = []
        for ratio, bi, cj in scored:
            if base_status[bi] is not None or compare_status[cj] is not None:
                continue
            # Não-cruzamento dentro do vão: reordenação local não é papel do
            # passo 2 (os órfãos restantes caem no passo 3, como movimentação).
            if any((bi2 - bi) * (cj2 - cj) < 0 for bi2, cj2 in accepted):
                continue
            accepted.append((bi, cj))
            hash_equal = (
                base_blocks[bi].content_hash() == compare_blocks[cj].content_hash()
            )
            # EQUAL exige texto idêntico (hash). Ratio alto (ex.: 0.99 num
            # parágrafo longo) ainda esconde uma edição real de uma palavra —
            # isso É um MODIFY (regressão flagrada no contrato Escorrega:
            # "operação"→"compra" sumia do redline).
            if hash_equal and not runs_have_formatting_diff(
                base_blocks[bi].runs, compare_blocks[cj].runs
            ):
                ct = ChangeType.EQUAL
            else:
                ct = ChangeType.MODIFY
            base_status[bi] = ct
            compare_status[cj] = ct
            base_pair[bi] = cj
            compare_pair[cj] = bi

    # Passo 3: detecção de movimentação entre órfãos restantes.
    for bi in range(n):
        if base_status[bi] is not None:
            continue
        best_j = -1
        best_ratio = MOVE_THRESHOLD
        for cj in range(m):
            if compare_status[cj] is not None:
                continue
            bb = base_blocks[bi]
            cb = compare_blocks[cj]
            if bb.content_hash() == cb.content_hash():
                ratio = 1.0
            else:
                ratio = _text_ratio(bb, cb)
            if ratio > MOVE_THRESHOLD and ratio >= best_ratio:
                best_ratio = ratio
                best_j = cj
        if best_j >= 0:
            hash_equal = (
                base_blocks[bi].content_hash() == compare_blocks[best_j].content_hash()
            )
            # MOVE "limpo" só com texto idêntico; qualquer edição real no
            # bloco movido precisa aparecer marcada (MOVE_MODIFY).
            ct = ChangeType.MOVE if hash_equal else ChangeType.MOVE_MODIFY
            base_status[bi] = ct
            compare_status[best_j] = ct
            base_pair[bi] = best_j
            compare_pair[best_j] = bi

    # Pós-passo 3: movimentação de verdade é INVERSÃO de ordem. Um par
    # "movido" que não cruza nenhuma outra âncora só foi deslocado por
    # inserções/exclusões vizinhas — rebaixa para EQUAL/MODIFY (princípio
    # do VISAO_GERAL: nada de falso-movido).
    matched_pairs = [
        (bi, base_pair[bi])
        for bi in range(n)
        if base_pair[bi] >= 0
    ]
    for bi in range(n):
        if base_status[bi] not in (ChangeType.MOVE, ChangeType.MOVE_MODIFY):
            continue
        cj = base_pair[bi]
        crosses = any(
            (bi2 - bi) * (cj2 - cj) < 0
            for bi2, cj2 in matched_pairs
            if bi2 != bi
        )
        if crosses:
            continue
        if base_status[bi] == ChangeType.MOVE:
            if runs_have_formatting_diff(
                base_blocks[bi].runs, compare_blocks[cj].runs
            ):
                downgraded = ChangeType.MODIFY
            else:
                downgraded = ChangeType.EQUAL
        else:
            downgraded = ChangeType.MODIFY
        base_status[bi] = downgraded
        compare_status[cj] = downgraded

    # Restante: exclusões e inserções.
    for bi in range(n):
        if base_status[bi] is None:
            base_status[bi] = ChangeType.DELETE
    for cj in range(m):
        if compare_status[cj] is None:
            compare_status[cj] = ChangeType.INSERT

    # Monta lista de alinhamentos.
    alignments: List[AlignedBlock] = []
    seen_compare: set = set()
    for bi in range(n):
        ct = base_status[bi]
        cj = base_pair[bi]
        if ct == ChangeType.DELETE:
            alignments.append(AlignedBlock(base_index=bi, compare_index=None, change_type=ct))
        elif cj >= 0 and cj not in seen_compare:
            alignments.append(
                AlignedBlock(base_index=bi, compare_index=cj, change_type=ct or ChangeType.EQUAL)
            )
            seen_compare.add(cj)
    for cj in range(m):
        if compare_status[cj] == ChangeType.INSERT:
            alignments.append(AlignedBlock(base_index=None, compare_index=cj, change_type=ChangeType.INSERT))

    return _render_order(alignments, base_pair, compare_pair, n, m)


def _delete_anchor(bi: int, compare_pair: List[int], m: int) -> int:
    """Posição no fluxo revisado onde uma exclusão deve aparecer."""
    for cj in range(m):
        paired_base = compare_pair[cj]
        if paired_base >= 0 and paired_base > bi:
            return cj
    return m


def _render_order(
    alignments: List[AlignedBlock],
    base_pair: List[int],
    compare_pair: List[int],
    n: int,
    m: int,
) -> List[AlignedBlock]:
    """Ordena para render_blocks: fluxo do doc revisado com exclusões intercaladas."""

    def sort_key(item: AlignedBlock) -> tuple:
        if item.compare_index is not None:
            return (item.compare_index, 0, item.base_index if item.base_index is not None else -1)
        anchor = _delete_anchor(item.base_index or 0, compare_pair, m)
        return (anchor, -1, item.base_index or 0)

    return sorted(alignments, key=sort_key)
