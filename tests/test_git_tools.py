import unittest
from code_agent.git_tools import GitTools

DIFF_SAMPLE = """diff --git a/app.py b/app.py
index 1234567..89abcdef 100644
--- a/app.py
+++ b/app.py
@@ -10,4 +10,6 @@ def main():
     print("start")
+    eval("malicious")
+    print("end")
"""

class TestGitTools(unittest.TestCase):
    def test_parse_unified_diff(self):
        file_diffs = GitTools.parse_unified_diff(DIFF_SAMPLE)
        self.assertEqual(len(file_diffs), 1)
        fd = file_diffs[0]
        self.assertEqual(fd.old_path, "app.py")
        self.assertEqual(fd.new_path, "app.py")
        self.assertEqual(len(fd.hunks), 1)

        # Line numbers of added lines
        changed_lines = fd.changed_line_numbers
        self.assertIn(11, changed_lines)
        self.assertIn(12, changed_lines)

if __name__ == "__main__":
    unittest.main()
