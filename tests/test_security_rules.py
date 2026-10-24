import unittest
from code_agent.security_rules import CodeRuleEngine

VULNERABLE_CODE = '''import os
import subprocess
import hashlib
import requests
import tempfile

def run_user_cmd(user_input):
    eval(user_input)
    os.system("ls " + user_input)
    subprocess.Popen("echo test", shell=True)

def query_db(cursor, name):
    cursor.execute(f"SELECT * FROM users WHERE name = '{name}'")

def insecure_crypto(data):
    return hashlib.md5(data.encode()).hexdigest()

def bad_exceptions():
    try:
        x = 1 / 0
    except:
        pass

    try:
        y = 2 / 0
    except Exception:
        pass

def fetch_data():
    requests.get("https://example.com", verify=False)
    tempfile.mktemp()

secret_token = "api_key = 'abcdef1234567890abcdef'"
'''

class TestSecurityRules(unittest.TestCase):
    def test_detection_of_flaws(self):
        findings = CodeRuleEngine.scan_content(VULNERABLE_CODE, file_path="test_vuln.py")
        rule_ids = {f.rule_id for f in findings}

        # Dynamic eval
        self.assertIn("SEC-001", rule_ids)
        # os.system
        self.assertIn("SEC-002", rule_ids)
        # subprocess shell=True
        self.assertIn("SEC-006", rule_ids)
        # SQL injection
        self.assertIn("SEC-007", rule_ids)
        # Weak hash md5
        self.assertIn("SEC-005", rule_ids)
        # Insecure SSL verify=False
        self.assertIn("SEC-008", rule_ids)
        # Insecure tempfile
        self.assertIn("SEC-009", rule_ids)
        # Bare except
        self.assertIn("CODE-001", rule_ids)
        # Silent exception suppression
        self.assertIn("CODE-002", rule_ids)
        # Secret token regex
        self.assertIn("SEC-101", rule_ids)

if __name__ == "__main__":
    unittest.main()
