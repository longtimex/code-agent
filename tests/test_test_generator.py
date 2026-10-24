import tempfile
import unittest
from pathlib import Path
from code_agent.test_generator import TestGenerator

SAMPLE_TARGET = '''
def add_numbers(x: int, y: int) -> int:
    """Add two numbers together."""
    return x + y

def validate_age(age: int) -> bool:
    if age < 0:
        raise ValueError("Age cannot be negative")
    return age >= 18
'''

class TestTestGenerator(unittest.TestCase):
    def test_generate_pytest_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "math_ops.py"
            target.write_text(SAMPLE_TARGET, encoding="utf-8")

            pytest_code = TestGenerator.generate_test_file(target, output_framework="pytest")
            self.assertIn("import pytest", pytest_code)
            self.assertIn("def test_add_numbers_happy_path", pytest_code)
            self.assertIn("def test_validate_age_edge_cases", pytest_code)

    def test_generate_unittest_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "math_ops.py"
            target.write_text(SAMPLE_TARGET, encoding="utf-8")

            unittest_code = TestGenerator.generate_test_file(target, output_framework="unittest")
            self.assertIn("import unittest", unittest_code)
            self.assertIn("class TestMath_ops(unittest.TestCase):", unittest_code)
            self.assertIn("def test_add_numbers_happy_path(self):", unittest_code)

if __name__ == "__main__":
    unittest.main()
