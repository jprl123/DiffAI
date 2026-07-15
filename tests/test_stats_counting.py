"""Regressão da contagem do Summary — inserções/exclusões devem contar
TRECHOS CONTÍNUOS (inclusive inline, células e linhas de tabela), não só
parágrafos inteiros (relatório Analise_Redline_Consolidado, testes 01–20)."""
from __future__ import annotations

import unittest

from app.engine.compare import _build_stats, _count_fragment_runs
from app.models import BlockKind, ChangeType, Fragment, RenderBlock


def _frag(text, op="equal"):
    return Fragment(text=text, op=op)


class FragmentRunCountingTests(unittest.TestCase):
    def test_runs_of_insert_and_delete(self):
        frags = [
            _frag("R$ 1"), _frag("2.0", "delete"), _frag("6.5", "insert"),
            _frag("00,00"), _frag(" novo", "insert"),
        ]
        ins, dele = _count_fragment_runs(frags)
        self.assertEqual((ins, dele), (2, 1))

    def test_empty(self):
        self.assertEqual(_count_fragment_runs([]), (0, 0))


class BuildStatsInlineTests(unittest.TestCase):
    def test_inline_and_table_are_counted(self):
        # Parágrafo MODIFY com troca inline de número (1 del + 1 ins).
        modify_para = RenderBlock(
            kind=BlockKind.PARAGRAPH, change_type=ChangeType.MODIFY,
            fragments=[_frag("R$ 1"), _frag("2.0", "delete"),
                       _frag("6.5", "insert"), _frag("00,00")],
        )
        # Parágrafo totalmente inserido (1 ins).
        insert_para = RenderBlock(
            kind=BlockKind.PARAGRAPH, change_type=ChangeType.INSERT,
            fragments=[_frag("Cláusula nova de arbitragem.", "insert")],
        )
        # Tabela: cabeçalho igual + 1 linha nova (1 ins) + 1 célula alterada
        # numa linha modify (1 del + 1 ins).
        table = RenderBlock(
            kind=BlockKind.TABLE, change_type=ChangeType.MODIFY,
            rows=[
                [[_frag("Parcela")], [_frag("Venc.")], [_frag("Valor")]],
                [[_frag("3")], [_frag("03/2025")],
                 [_frag("R$ 12.0"), _frag("2.0", "delete"),
                  _frag("3.2", "insert"), _frag("00,00")]],
                [[_frag("7", "insert")], [_frag("07/2026", "insert")],
                 [_frag("R$ 12.000,00", "insert")]],
            ],
            row_ops=["equal", "modify", "insert"],
        )
        stats = _build_stats([], [], [modify_para, insert_para, table])
        # ins: inline número (1) + parágrafo (1) + célula alterada (1) + linha nova (1) = 4
        # del: inline número (1) + célula alterada (1) = 2
        self.assertEqual(stats.insertions, 4)
        self.assertEqual(stats.deletions, 2)
        self.assertEqual(stats.total_changes, stats.insertions + stats.deletions + stats.moves)

    def test_moved_block_counts_only_as_move_not_insertion(self):
        move = RenderBlock(
            kind=BlockKind.PARAGRAPH, change_type=ChangeType.MOVE,
            fragments=[_frag("Cláusula movida", "insert")],  # não deve virar inserção
        )
        stats = _build_stats([], [], [move])
        self.assertEqual(stats.insertions, 0)
        self.assertEqual(stats.deletions, 0)


if __name__ == "__main__":
    unittest.main()
