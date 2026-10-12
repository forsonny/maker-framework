"""Focused regression checks for projects without a supported QA runner."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from qa_server.__main__ import create_server
from qa_server.adapter_factory import ADAPTER_MAP, NoSupportedFramework, get_adapter
from qa_server.config import QAConfig
from qa_server.server import _detect_tool_error
from qa_server.tools.check_regressions import check_regressions_handler
from qa_server.tools.get_coverage import get_coverage_handler
from qa_server.tools.run_tests import run_tests_handler

ROOT = Path(__file__).resolve().parents[1]


class QARoutingChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="maker routing ")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        env = patch.dict(os.environ, {"QA_ALLOWED_PATHS": self.temp.name})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("QA_CONFIG_PATH", None)
        os.environ.pop("MAKER_QA_WORKSPACE_MODE", None)
        (self.project / "index.html").write_text('<script src="app.js"></script>', encoding="utf-8")
        (self.project / "app.js").write_text("console.log('Browser app');", encoding="utf-8")
        (self.project / "package.json").write_text(
            json.dumps({"scripts": {"start": "node app.js"}}), encoding="utf-8")

    def arguments(self, **kwargs):
        return {"working_dir": str(self.project), **kwargs}

    def snapshot(self):
        return {str(path.relative_to(self.project)): path.read_bytes()
                for path in self.project.rglob("*") if path.is_file()}

    def assert_unavailable(self, result):
        self.assertEqual(result["status"], "unavailable", result)
        self.assertEqual(result["code"], "NO_SUPPORTED_TEST_FRAMEWORK", result)
        self.assertEqual(result["tests_executed"], 0, result)
        self.assertIn("No tests were executed", result["message"])
        self.assertIn("manual acceptance workflow", result["message"])
        self.assertTrue(_detect_tool_error(result))

    def test_no_runner_does_not_spawn_or_write_artifacts(self):
        baseline = self.project / "qa-reports" / "baseline.json"
        baseline.parent.mkdir()
        baseline.write_text('{"tests":{"accepted":"PASS"},"flaky_counts":{}}', encoding="utf-8")
        before = self.snapshot()
        with patch("subprocess.run") as run, patch("subprocess.Popen") as popen:
            with self.assertRaises(NoSupportedFramework):
                get_adapter(working_dir=str(self.project))
            tests = run_tests_handler(self.arguments())
            coverage = get_coverage_handler(self.arguments(threshold=0))
            regressions = check_regressions_handler(self.arguments(update_baseline=True))
        run.assert_not_called()
        popen.assert_not_called()
        for result in (tests, coverage, regressions):
            self.assert_unavailable(result)
        self.assertEqual((tests["passed"], tests["failed"], tests["total"]), (0, 0, 0))
        self.assertEqual(tests["failures"], [])
        self.assertIsNone(coverage["percentage"])
        self.assertFalse(coverage["meets_threshold"])
        self.assertEqual(coverage["uncovered_lines"], [])
        self.assertEqual(regressions["regressions"], [])
        self.assertEqual(regressions["missing_tests"], [])
        self.assertEqual(regressions["unchanged"], 0)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.project / ".pytest_cache").exists())

    def test_no_runner_does_not_create_automatic_baseline(self):
        before = self.snapshot()
        with patch("subprocess.run") as run, patch("subprocess.Popen") as popen:
            result = check_regressions_handler(self.arguments())
        self.assert_unavailable(result)
        run.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.project / "qa-reports").exists())

    def test_explicit_frameworks_bypass_detection(self):
        config = QAConfig()
        with patch("subprocess.run") as run:
            for framework, adapter_class in ADAPTER_MAP.items():
                with self.subTest(framework=framework), patch.object(adapter_class, "detect") as detect:
                    config.test.framework = framework
                    adapter = get_adapter(config, working_dir=str(self.project))
                    self.assertIsInstance(adapter, adapter_class)
                    detect.assert_not_called()
            config.test.framework = "unsupported"
            with self.assertRaises(ValueError) as caught:
                get_adapter(config, working_dir=str(self.project))
            self.assertNotIsInstance(caught.exception, NoSupportedFramework)
        run.assert_not_called()

    def test_supported_runner_reports_real_pass_and_failure(self):
        (self.project / "test_sample.py").write_text(
            "import unittest\nclass Sample(unittest.TestCase):\n"
            "    def test_pass(self): self.assertEqual(1 + 1, 2)\n"
            "    def test_fail(self): self.assertEqual(1 + 1, 3)\n", encoding="utf-8")
        frameworks = ["unittest"]
        if importlib.util.find_spec("pytest"):
            frameworks.append("auto")
        for framework in frameworks:
            with self.subTest(framework=framework):
                result = run_tests_handler(self.arguments(framework=framework))
                self.assertEqual((result["passed"], result["failed"], result["total"]), (1, 1, 2), result)
                self.assertEqual(len(result["failures"]), 1, result)
                self.assertIn("test_fail", result["failures"][0]["name"])
                self.assertNotEqual(result.get("status"), "unavailable")
                self.assertFalse(_detect_tool_error(result))

    def test_unavailable_mcp_results_are_errors_without_product_failures(self):
        server = create_server()
        server._initialized = True
        before = self.snapshot()
        with patch("subprocess.run") as run, patch("subprocess.Popen") as popen:
            for tool in ("run_tests", "get_coverage", "check_regressions"):
                with self.subTest(tool=tool):
                    wrapped = server.handle_tools_call({"name": tool, "arguments": self.arguments()})
                    self.assertTrue(wrapped["isError"], wrapped)
                    self.assert_unavailable(json.loads(wrapped["content"][0]["text"]))
        run.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_unavailable_cli_returns_nonzero_and_structured_result(self):
        before = self.snapshot()
        for tool in ("run_tests", "get_coverage", "check_regressions"):
            with self.subTest(tool=tool):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "qa.py"), "--workspace", str(self.project),
                     "--tool", tool], capture_output=True, text=True, encoding="utf-8", timeout=10)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assert_unavailable(json.loads(result.stdout))
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
