import tempfile
import unittest
from pathlib import Path
from code_agent.debt_estimator import DebtEstimator

class TestDebtEstimator(unittest.TestCase):
    def test_maintainability_index(self):
        mi, grade = DebtEstimator.calculate_maintainability_index(loc=50, complexity=5)
        self.assertGreaterEqual(mi, 40.0)
        self.assertIn(grade, ["A", "B", "C"])

    def test_duplicate_code_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create two files sharing a 5-line block
            shared_chunk = (
                "def helper_action():\n"
                "    a = 1 + 2\n"
                "    b = 3 + 4\n"
                "    c = a * b\n"
                "    return c\n"
            )

            (root / "file1.py").write_text(shared_chunk, encoding="utf-8")
            (root / "file2.py").write_text(shared_chunk, encoding="utf-8")

            dups = DebtEstimator.find_duplicates([root / "file1.py", root / "file2.py"], min_lines=4)
            self.assertGreaterEqual(len(dups), 1)
            self.assertEqual(len(dups[0].instances), 2)

if __name__ == "__main__":
    unittest.main()
