"""Regressão do Summary em pares PDF×PDF (testes 46–50 do Mentone).

Cada par v1/v2 tem alterações controladas; o Summary do app deve bater com o
GABARITO (tests/fixtures/summary_pdf/GABARITO.md). Roda o pipeline REAL de PDF
(pdf2docx → extração DOCX → motor de comparação), que é onde a fragmentação de
parágrafo, a partição de tabela e a contagem de movimento por parágrafo
inflavam a contagem. NÃO precisa de LibreOffice (só o modelo/estatística).

Pulado automaticamente se o pdf2docx não estiver instalado.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import unittest

logging.disable(logging.CRITICAL)

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "summary_pdf")

try:
    import pdf2docx  # noqa: F401
    import fitz  # noqa: F401
    _HAVE_PDF = True
except Exception:  # pragma: no cover
    _HAVE_PDF = False

# (stem, inserções, exclusões, movimentações, total) — do GABARITO.md.
_CASES = [
    ("Teste_46_Consultoria", 4, 3, 1, 8),
    ("Teste_47_Licenciamento", 4, 4, 0, 8),
    ("Teste_48_Locacao", 3, 3, 1, 7),
    ("Teste_49_Fornecimento", 5, 3, 1, 9),
    ("Teste_50_NDA", 2, 2, 1, 5),
]


@unittest.skipUnless(_HAVE_PDF, "pdf2docx/PyMuPDF indisponível")
class SummaryPdfPairsTests(unittest.TestCase):
    def _run_pair(self, stem):
        from app.extract.pdf_to_docx import convert_pdf_to_docx
        from app.extract.loader import load_document
        from app.engine.compare import compare_documents

        v1 = os.path.join(_FIX, "v1", stem + "_v1.pdf")
        v2 = os.path.join(_FIX, "v2", stem + "_v2.pdf")
        tmp = tempfile.mkdtemp(prefix="test-summary-pdf-")
        try:
            b = os.path.join(tmp, "b.docx")
            c = os.path.join(tmp, "c.docx")
            convert_pdf_to_docx(v1, b)
            convert_pdf_to_docx(v2, c)
            result = compare_documents(load_document(b), load_document(c))
            return result.stats
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_summary_matches_gabarito(self):
        for stem, ins, dele, mov, total in _CASES:
            with self.subTest(par=stem):
                s = self._run_pair(stem)
                self.assertEqual(
                    (s.insertions, s.deletions, s.moves, s.total_changes),
                    (ins, dele, mov, total),
                    "Summary de %s: app=(ins=%d del=%d mov=%d tot=%d) "
                    "gabarito=(ins=%d del=%d mov=%d tot=%d)" % (
                        stem, s.insertions, s.deletions, s.moves,
                        s.total_changes, ins, dele, mov, total,
                    ),
                )


if __name__ == "__main__":
    unittest.main()
