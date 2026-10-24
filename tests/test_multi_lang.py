import unittest
from code_agent.multi_lang import MultiLangScanner

JS_VULN = """
function render(userInput) {
    document.getElementById("output").innerHTML = userInput;
    eval(userInput);
    const cp = require("child_process");
    cp.exec("ping " + userInput);
}
"""

GO_VULN = """
package main

import (
    "crypto/tls"
    "database/sql"
    "fmt"
)

func query(db *sql.DB, input string) {
    conf := &tls.Config{InsecureSkipVerify: true}
    db.Query(fmt.Sprintf("SELECT * FROM users WHERE id = %s", input))
}
"""

SHELL_VULN = """#!/bin/bash
curl https://example.com/install.sh | bash
rm -rf $TARGET_DIR
eval "$USER_CMD"
"""

class TestMultiLangScanner(unittest.TestCase):
    def test_javascript_vulnerabilities(self):
        findings = MultiLangScanner.scan_content(JS_VULN, file_path="app.js")
        rules = {f.rule_id for f in findings}
        self.assertIn("SEC-JS-001", rules)  # innerHTML
        self.assertIn("SEC-JS-002", rules)  # eval
        self.assertIn("SEC-JS-003", rules)  # child_process.exec

    def test_go_vulnerabilities(self):
        findings = MultiLangScanner.scan_content(GO_VULN, file_path="main.go")
        rules = {f.rule_id for f in findings}
        self.assertIn("SEC-GO-001", rules)  # InsecureSkipVerify
        self.assertIn("SEC-GO-002", rules)  # fmt.Sprintf in query

    def test_shell_vulnerabilities(self):
        findings = MultiLangScanner.scan_content(SHELL_VULN, file_path="deploy.sh")
        rules = {f.rule_id for f in findings}
        self.assertIn("SEC-SH-001", rules)  # curl | bash
        self.assertIn("SEC-SH-002", rules)  # rm -rf $VAR
        self.assertIn("SEC-SH-003", rules)  # eval $VAR

if __name__ == "__main__":
    unittest.main()
