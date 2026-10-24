import tempfile
import unittest
from pathlib import Path
from code_agent.call_graph import DependencyGraph

class TestCallGraph(unittest.TestCase):
    def test_dependency_and_callers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # File A defines a helper and calls it
            mod_a = root / "module_a.py"
            mod_a.write_text(
                'def calculate_total(price, tax):\n'
                '    return price + tax\n',
                encoding="utf-8"
            )

            # File B imports File A and calls calculate_total
            mod_b = root / "module_b.py"
            mod_b.write_text(
                'from module_a import calculate_total\n\n'
                'def process_order():\n'
                '    return calculate_total(100, 10)\n',
                encoding="utf-8"
            )

            graph = DependencyGraph(root_dir=root)
            callers = graph.find_callers("calculate_total")

            self.assertEqual(len(callers), 1)
            self.assertEqual(callers[0].caller_function, "process_order")
            self.assertIn("module_b.py", callers[0].caller_file)

            # Test blast radius: if module_a.py changes, module_b.py is in the blast radius
            blast = graph.get_blast_radius("module_a.py")
            self.assertIn("module_b.py", blast)

if __name__ == "__main__":
    unittest.main()
