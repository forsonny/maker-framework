"""Regression checks for the failures reproduced during the Codex port."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from qa_server.config import load_config
from qa_server.tools.run_tests import run_tests_handler
from qa_server.tools.get_coverage import get_coverage_handler
from qa_server.tools.generate_tests import generate_tests_handler
from qa_server.tools.check_regressions import check_regressions_handler
from qa_server.tools.check_prd_alignment import check_prd_alignment_handler
from qa_server.tools.aggregate_qa_report import aggregate_qa_report_handler

ROOT = Path(__file__).resolve().parents[1]


class QAChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="maker qa ")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"QA_ALLOWED_PATHS": self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        (self.project / "sample.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        self.write_tests(False)

    def write_tests(self, failing):
        expected = 400 if failing else 3  # Different byte length avoids stale timestamp-based pyc reuse.
        (self.project / "test_sample.py").write_text(
            "import unittest\nfrom sample import add\nclass Sample(unittest.TestCase):\n"
            "    def test_first(self): self.assertEqual(add(1, 2), 3)\n"
            f"    def test_second(self): self.assertEqual(add(1, 2), {expected})\n",
            encoding="utf-8")

    def arguments(self, **kwargs):
        return {"working_dir": str(self.project), "framework": "unittest", **kwargs}

    def test_unittest_defaults_and_named_failures(self):
        passed = run_tests_handler(self.arguments())
        self.assertEqual((passed["passed"], passed["failed"]), (2, 0), passed)
        self.assertEqual(len(passed["passed_names"]), 2)
        self.write_tests(True)
        result = run_tests_handler(self.arguments())
        self.assertEqual((result["passed"], result["failed"]), (1, 1), result)
        self.assertEqual(len(result["failures"]), 1)

    @unittest.skipUnless(importlib.util.find_spec("pytest"), "pytest not installed")
    def test_pytest_defaults_glob_and_regression_names(self):
        result = run_tests_handler(self.arguments(framework="pytest", pattern="**/test_*.py"))
        self.assertEqual(result["passed"], 2, result)
        self.assertEqual(len(result["passed_names"]), 2, result)
        missing = run_tests_handler(self.arguments(framework="pytest", pattern="missing_*.py"))
        self.assertEqual(missing["passed"], 0)
        self.assertTrue(missing["failures"])

    def test_project_config_is_read_and_overrides_do_not_leak(self):
        (self.project / "qa-config.yaml").write_text("test:\n  framework: unittest\n  timeout_seconds: 42\n")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QA_CONFIG_PATH", None)
            run_tests_handler(self.arguments(timeout=3))
            config = load_config(working_dir=str(self.project), use_cache=False)
            self.assertEqual(config.test.timeout_seconds, 42)
            self.assertEqual(config.test.framework, "unittest")

    def test_relative_generation_preserves_existing_tests(self):
        args = {"working_dir": str(self.project), "source_files": ["sample.py"], "framework": "pytest"}
        generated = generate_tests_handler({**args, "write_files": False})
        self.assertEqual(generated["total_tests"], 1, generated)
        self.assertIn("pytest.skip", generated["generated_files"][0]["content"])
        (self.project / "tests").mkdir()
        target = self.project / "tests" / "test_sample.py"
        target.write_text("# existing assertions\n")
        result = generate_tests_handler(args)
        self.assertFalse(result["generated_files"][0]["written"])
        self.assertEqual(target.read_text(), "# existing assertions\n")

    def test_regression_baseline_relative_to_project(self):
        args = self.arguments(baseline="qa-reports/baseline.json", update_baseline=True)
        check_regressions_handler(args)
        self.assertTrue((self.project / "qa-reports/baseline.json").is_file())
        self.write_tests(True)
        result = check_regressions_handler({**args, "update_baseline": False})
        self.assertEqual(len(result["regressions"]), 1, result)
        self.assertEqual(result["regressions"][0]["previous_status"], "PASS")

    @unittest.skipUnless(importlib.util.find_spec("coverage"), "coverage not installed")
    def test_coverage_collects_project_source(self):
        result = get_coverage_handler(self.arguments())
        self.assertTrue(result["meets_threshold"], result)
        self.assertGreater(result["percentage"], 0)

    def test_prd_and_aggregation_are_callable(self):
        (self.project / "PRD.md").write_text("The system must return numbers added together.\n")
        result = check_prd_alignment_handler({"working_dir": str(self.project), "prd_path": "PRD.md",
                                              "implementation_paths": ["sample.py"]})
        self.assertEqual(result["total_requirements"], 1)
        self.assertEqual(result["files_analyzed"], 1)
        summary = aggregate_qa_report_handler({"stage_results": [{"stage_name": "test", "passed": 2, "failed": 1}]})
        self.assertNotEqual(summary["overall_status"], "PASS")
        empty = aggregate_qa_report_handler({"stage_results": []})
        self.assertEqual(empty["overall_status"], "FAIL")

    def test_stdio_handshake_tools_and_eof(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "ping", "arguments": {}}},
        ]
        result = subprocess.run([sys.executable, str(ROOT / "scripts/qa.py"), "--workspace", str(self.project)],
                                input="".join(json.dumps(r) + "\n" for r in requests), capture_output=True,
                                text=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = {r["id"]: r for r in map(json.loads, result.stdout.splitlines())}
        self.assertEqual(len(responses[2]["result"]["tools"]), 7)
        self.assertFalse(responses[3]["result"]["isError"])

    def test_global_server_selects_two_projects_and_requires_absolute_target(self):
        with tempfile.TemporaryDirectory(prefix="maker second project ") as other:
            (Path(other) / "test_other.py").write_text(
                "import unittest\nclass Other(unittest.TestCase):\n    def test_failure(self): self.fail('expected')\n")
            def call(i, arguments):
                return {"jsonrpc": "2.0", "id": i, "method": "tools/call",
                        "params": {"name": "run_tests", "arguments": arguments}}
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                call(3, self.arguments()),
                call(4, {"working_dir": other, "framework": "unittest"}),
                call(5, {"framework": "unittest"}),
                call(6, {"working_dir": ".", "framework": "unittest"}),
            ]
            result = subprocess.run([sys.executable, str(ROOT / "scripts/qa.py"), "--global"],
                                    input="".join(json.dumps(r) + "\n" for r in requests), capture_output=True,
                                    text=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = {r["id"]: r for r in map(json.loads, result.stdout.splitlines())}
        tools = {t["name"]: t for t in responses[2]["result"]["tools"]}
        self.assertIn("working_dir", tools["run_tests"]["inputSchema"]["required"])
        first = json.loads(responses[3]["result"]["content"][0]["text"])
        second = json.loads(responses[4]["result"]["content"][0]["text"])
        self.assertEqual((first["passed"], first["failed"]), (2, 0), first)
        self.assertEqual((second["passed"], second["failed"]), (0, 1), second)
        self.assertIn("error", responses[5])
        self.assertTrue(responses[6]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
