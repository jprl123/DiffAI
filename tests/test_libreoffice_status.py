"""Status / detecção do LibreOffice (sem exigir instalação)."""
from __future__ import annotations

import unittest
from unittest import mock

from app.output.docx_to_pdf import (
    LIBREOFFICE_DOWNLOAD_URL,
    find_soffice,
    libreoffice_status,
)


class LibreOfficeStatusTests(unittest.TestCase):
    def test_download_url_is_official(self) -> None:
        self.assertIn("libreoffice.org", LIBREOFFICE_DOWNLOAD_URL)

    def test_status_shape_when_missing(self) -> None:
        with mock.patch("app.output.docx_to_pdf.find_soffice", return_value=None):
            st = libreoffice_status()
        self.assertFalse(st["installed"])
        self.assertIsNone(st["path"])
        self.assertIsNone(st["version"])
        self.assertEqual(st["download_url"], LIBREOFFICE_DOWNLOAD_URL)
        self.assertIn("platform", st)

    def test_find_soffice_prefers_mac_app_path(self) -> None:
        mac = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        with mock.patch("app.output.docx_to_pdf.sys.platform", "darwin"), mock.patch(
            "app.output.docx_to_pdf.os.path.isfile",
            side_effect=lambda p: p == mac,
        ), mock.patch("app.output.docx_to_pdf.shutil.which", return_value=None):
            self.assertEqual(find_soffice(), mac)


if __name__ == "__main__":
    unittest.main()
