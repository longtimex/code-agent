import tempfile
import unittest
from pathlib import Path
from code_agent.cache import IncrementalCache
from code_agent.models import Finding

class TestCache(unittest.TestCase):
    def test_cache_hit_and_invalidation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            f = root / "service.py"
            f.write_text("def ping(): pass\n", encoding="utf-8")

            cache = IncrementalCache(root)
            self.assertIsNone(cache.get_cached(f))

            # Update cache
            dummy_findings = [
                Finding(
                    rule_id="RULE-1",
                    title="Test",
                    severity="LOW",
                    file_path=str(f),
                    line_number=1,
                    snippet="def ping(): pass",
                    recommendation="None",
                )
            ]
            cache.update(f, dummy_findings)
            cache.save()

            # Cache hit
            cached = cache.get_cached(f)
            self.assertIsNotNone(cached)
            self.assertEqual(len(cached), 1)
            self.assertEqual(cached[0].rule_id, "RULE-1")

            # Modify file => Cache invalidation
            f.write_text("def ping(): return True\n", encoding="utf-8")
            self.assertIsNone(cache.get_cached(f))

if __name__ == "__main__":
    unittest.main()
