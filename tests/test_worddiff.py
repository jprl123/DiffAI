"""Testes do worddiff — coalescência estilo Word Compare."""
from __future__ import annotations

import unittest

from app.engine.worddiff import worddiff_runs
from app.models import Run


def _runs(text: str) -> list:
    return [Run(text=text)]


def _ops(fragments) -> list:
    return [(f.op, f.text) for f in fragments]


class WorddiffCoalesceTests(unittest.TestCase):
    def test_bracket_wrap_is_contiguous_replace(self) -> None:
        base = "casado sob o regime da comunhão parcial de bens"
        rev = "[casado sob o regime da comunhão parcial de bens]"
        fr = worddiff_runs(_runs(base), _runs(rev))
        # Um delete da frase inteira + um insert da frase com brackets —
        # sem âncoras equal no meio ("sob", "regime", …).
        self.assertEqual(
            _ops(fr),
            [("delete", base), ("insert", rev)],
        )

    def test_bracket_wrap_long_legal_phrase(self) -> None:
        base = (
            "casada sob o regime da comunhão universal de bens "
            "anterior à Lei nº 6.515/77"
        )
        rev = "[%s]" % base
        fr = worddiff_runs(_runs(base), _runs(rev))
        self.assertEqual(_ops(fr), [("delete", base), ("insert", rev)])

    def test_phrase_rewrite_stays_contiguous(self) -> None:
        base = "por seus representantes legais"
        rev = "representada nos termos de seu Contrato Social"
        fr = worddiff_runs(_runs(base), _runs(rev))
        ops = [f.op for f in fr]
        # Não deve intercalear equal entre delete/insert no meio da frase.
        self.assertNotIn("equal", ops)
        self.assertEqual(ops, ["delete", "insert"])

    def test_distant_stable_text_not_absorbed(self) -> None:
        # Duas mudanças com um trecho longo estável no meio (>12 palavras)
        # devem preservar o equal central.
        mid = " ".join("palavra%d" % i for i in range(20))
        base = "ALPHA %s OMEGA" % mid
        rev = "BETA %s ZETA" % mid
        fr = worddiff_runs(_runs(base), _runs(rev))
        equal_text = "".join(f.text for f in fr if f.op == "equal")
        self.assertIn("palavra10", equal_text)
        self.assertTrue(any(f.op == "equal" for f in fr))

    def test_simple_token_replace_unchanged(self) -> None:
        fr = worddiff_runs(_runs("São Luís-MA,"), _runs("São Luís/MA,"))
        self.assertEqual(
            _ops(fr),
            [("equal", "São "), ("delete", "Luís-MA,"), ("insert", "Luís/MA,")],
        )

    def test_identical_is_equal(self) -> None:
        fr = worddiff_runs(_runs("texto igual"), _runs("texto igual"))
        self.assertEqual(_ops(fr), [("equal", "texto igual")])

    def test_whitespace_bridge_absorbed(self) -> None:
        # Dois replaces separados só por espaço → um replace contíguo.
        base = "foo bar"
        rev = "baz qux"
        fr = worddiff_runs(_runs(base), _runs(rev))
        self.assertEqual(_ops(fr), [("delete", base), ("insert", rev)])


if __name__ == "__main__":
    unittest.main()
