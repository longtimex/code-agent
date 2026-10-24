import unittest
from code_agent.pr_reviewer import PRReviewer

class TestPRReviewer(unittest.TestCase):
    def test_generate_review_comment(self):
        comment = PRReviewer.generate_review_comment()
        self.assertIn("Code Analysis Agent", comment)
        self.assertIn("PR", comment)

if __name__ == "__main__":
    unittest.main()
