import tempfile
import unittest
from pathlib import Path

from code_agent.license_checker import LicenseChecker


class TestLicenseChecker(unittest.TestCase):
    def test_detect_mit_license_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lic_file = root / "LICENSE"
            lic_file.write_text("MIT License\n\nCopyright (c) 2026 Test\n", encoding="utf-8")

            report = LicenseChecker.audit(root)
            self.assertTrue(report.has_license_file)
            self.assertEqual(report.license_file_name, "LICENSE")
            self.assertIn("MIT", report.detected_licenses)
            self.assertEqual(len(report.risk_warnings), 0)

    def test_detect_spdx_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            code_file = root / "core.py"
            code_file.write_text(
                "# SPDX-License-Identifier: Apache-2.0\n\ndef main():\n    pass\n",
                encoding="utf-8",
            )

            report = LicenseChecker.audit(root)
            self.assertIn("Apache-2.0", report.detected_licenses)
            self.assertEqual(report.files_with_spdx, 1)

    def test_copyleft_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lic_file = root / "LICENSE"
            lic_file.write_text("GNU General Public License v3.0\n", encoding="utf-8")

            report = LicenseChecker.audit(root)
            self.assertIn("GPL-3.0", report.detected_licenses)
            self.assertTrue(any("强传染性开源协议" in w for w in report.risk_warnings))


if __name__ == "__main__":
    unittest.main()
