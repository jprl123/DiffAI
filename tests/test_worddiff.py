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
    # REGRA DO PRODUTO (usuário, mantida em 2026-07-15): regra dos 30% —
    # mudança pequena (≤30% dos chars) recebe marca FINA de caractere;
    # texto idêntico no meio permanece equal (não vira del+ins). Os testes
    # abaixo fixam esse comportamento.
    def test_bracket_wrap_marks_only_the_brackets(self) -> None:
        base = "casado sob o regime da comunhão parcial de bens"
        rev = "[%s]" % base
        fr = worddiff_runs(_runs(base), _runs(rev))
        # Miolo idêntico fica equal; só os colchetes entram.
        self.assertEqual(_ops(fr), [("insert", "["), ("equal", base), ("insert", "]")])

    def test_bracket_wrap_long_keeps_phrase_equal(self) -> None:
        base = (
            "casada sob o regime da comunhão universal de bens "
            "anterior à Lei nº 6.515/77"
        )
        rev = "[%s]" % base
        fr = worddiff_runs(_runs(base), _runs(rev))
        # A frase permanece equal; o token numérico final (com o "]" colado)
        # troca por inteiro — nunca dígito a dígito.
        self.assertEqual(_ops(fr), [
            ("insert", "["),
            ("equal", "casada sob o regime da comunhão universal de bens "
                      "anterior à Lei nº "),
            ("delete", "6.515/77"), ("insert", "6.515/77]"),
        ])

    def test_phrase_rewrite_keeps_shared_word(self) -> None:
        base = "por seus representantes legais"
        rev = "representada nos termos de seu Contrato Social"
        fr = worddiff_runs(_runs(base), _runs(rev))
        ops = _ops(fr)
        # "seus"→"seu" é par de 1 char (25% ≤ 30%): "seu" fica equal, "s" sai.
        self.assertIn(("equal", "seu"), ops)
        self.assertIn(("delete", "s"), ops)
        joined_del = "".join(t for o, t in ops if o == "delete")
        joined_ins = "".join(t for o, t in ops if o == "insert")
        self.assertIn("representantes legais", joined_del)
        self.assertIn("Contrato Social", joined_ins)

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

    def test_simple_token_char_refined(self) -> None:
        # Regra 30%: mudança de 1 char → marca fina (só "-"→"/"), resto equal.
        fr = worddiff_runs(_runs("São Luís-MA,"), _runs("São Luís/MA,"))
        self.assertEqual(
            _ops(fr),
            [("equal", "São Luís"), ("delete", "-"), ("insert", "/"), ("equal", "MA,")],
        )

    def test_number_replaced_whole_not_digit_by_digit(self) -> None:
        # Valor monetário trocado sai INTEIRO (não "R$ 12.06.500,00").
        fr = worddiff_runs(_runs("R$ 12.000,00"), _runs("R$ 16.500,00"))
        self.assertEqual(
            _ops(fr),
            [("equal", "R$ "), ("delete", "12.000,00"), ("insert", "16.500,00")],
        )

    def test_year_replaced_whole(self) -> None:
        # Data trocada sai inteira (não "20256").
        fr = worddiff_runs(_runs("de 2025"), _runs("de 2026"))
        self.assertEqual(
            _ops(fr), [("equal", "de "), ("delete", "2025"), ("insert", "2026")]
        )

    def test_percent_replaced_whole(self) -> None:
        fr = worddiff_runs(_runs("reajuste de 4%"), _runs("reajuste de 7%"))
        self.assertEqual(
            _ops(fr),
            [("equal", "reajuste de "), ("delete", "4%"), ("insert", "7%")],
        )

    def test_identical_is_equal(self) -> None:
        fr = worddiff_runs(_runs("texto igual"), _runs("texto igual"))
        self.assertEqual(_ops(fr), [("equal", "texto igual")])

    def test_whitespace_bridge_whole_replace(self) -> None:
        # Nenhum par ≤30% → troca inteira, ordem convencional delete→insert.
        base = "foo bar"
        rev = "baz qux"
        fr = worddiff_runs(_runs(base), _runs(rev))
        self.assertEqual(_ops(fr), [("delete", base), ("insert", rev)])


if __name__ == "__main__":
    unittest.main()
