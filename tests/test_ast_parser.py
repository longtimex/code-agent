import unittest
from code_agent.ast_parser import ASTParser

SAMPLE_CODE = '''"""Module docstring."""

def simple_func(x: int, y: str = "default") -> bool:
    """A simple function."""
    if x > 10 and y == "test":
        return True
    elif x < 0:
        return False
    return True

class Calculator:
    """Math calculator."""

    def add(self, a: float, b: float) -> float:
        return a + b

    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Division by zero")
        return a / b
'''

class TestASTParser(unittest.TestCase):
    def test_symbol_extraction(self):
        symbols = ASTParser.parse_source(SAMPLE_CODE)
        names = [s.name for s in symbols]
        self.assertIn("simple_func", names)
        self.assertIn("Calculator", names)
        self.assertIn("Calculator.add", names)
        self.assertIn("Calculator.divide", names)

    def test_complexity_calculation(self):
        symbols = ASTParser.parse_source(SAMPLE_CODE)
        func_sym = next(s for s in symbols if s.name == "simple_func")
        # simple_func has 'if' (1), 'and' (1), 'elif' (1) => base 1 + 3 = 4
        self.assertGreaterEqual(func_sym.complexity, 3)

    def test_signature_extraction(self):
        symbols = ASTParser.parse_source(SAMPLE_CODE)
        func_sym = next(s for s in symbols if s.name == "simple_func")
        self.assertIn("def simple_func(x: int, y: str = 'default') -> bool", func_sym.signature)

    def test_skeleton_generation(self):
        skeleton = ASTParser.get_skeleton(SAMPLE_CODE)
        self.assertIn("Module docstring", skeleton)
        self.assertIn("def simple_func", skeleton)
        self.assertIn("class Calculator", skeleton)
        self.assertIn("...", skeleton)
        # Full function body statements should be hidden
        self.assertNotIn("raise ValueError", skeleton)

    def test_extract_symbol_source(self):
        code = ASTParser.extract_symbol_source(SAMPLE_CODE, "Calculator.divide")
        self.assertIsNotNone(code)
        self.assertIn("def divide(self, a: float, b: float) -> float:", code)
        self.assertIn('raise ValueError("Division by zero")', code)

if __name__ == "__main__":
    unittest.main()
