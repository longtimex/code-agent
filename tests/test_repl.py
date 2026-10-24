import unittest
from code_agent.repl import InteractiveREPL

class TestREPL(unittest.TestCase):
    def test_repl_commands(self):
        repl = InteractiveREPL()
        # Test help command
        self.assertTrue(repl.handle_command("/help"))
        # Test diff command
        self.assertTrue(repl.handle_command("/diff"))
        # Test exit command returns False
        self.assertFalse(repl.handle_command("/exit"))

if __name__ == "__main__":
    unittest.main()
