"""Focused checks for project-owned test commands and their evidence limits."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from qa_server.__main__ import create_server
from qa_server.config import load_config
from qa_server.tools.aggregate_qa_report import aggregate_qa_report_handler
from qa_server.tools.check_regressions import check_regressions_handler
from qa_server.tools.get_coverage import get_coverage_handler
from qa_server.tools.run_tests import run_tests_handler

ROOT = Path(__file__).resolve().parents[1]


class ProjectCommandChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="maker command project ")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        env = patch.dict(os.environ, {"QA_ALLOWED_PATHS": self.temp.name})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("QA_CONFIG_PATH", None)
        os.environ.pop("MAKER_QA_WORKSPACE_MODE", None)

    def configure(self, command, **options):
        (self.project / "qa-config.yaml").write_text(
            json.dumps({"test": {"command": command, **options}}), encoding="utf-8")

    def script(self, source):
        (self.project / "project tests.py").write_text(source, encoding="utf-8")
        return [sys.executable, "project tests.py"]

    def call(self, tool="run_tests", **arguments):
        server = create_server()
        server._initialized = True
        wrapped = server.handle_tools_call({"name": tool, "arguments": {
            "working_dir": str(self.project), **arguments}})
        return wrapped, json.loads(wrapped["content"][0]["text"])

    def test_auto_command_preserves_arguments_output_and_unknown_counts(self):
        command = self.script("import json, os, sys\nprint(json.dumps([os.getcwd(), sys.argv[1:]]))\n"
                              "print('diagnostic', file=sys.stderr)\n")
        args = ["space value", "a&b", "$literal", "", 'a"quote']
        self.configure(command + args)
        # A supported framework marker must not override the project command.
        (self.project / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        wrapped, result = self.call()
        self.assertFalse(wrapped["isError"], result)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(json.loads(result["stdout"]), [str(self.project), args])
        self.assertIn("diagnostic", result["stderr"])
        self.assertFalse(result["test_counts_known"])
        self.assertIsNone(result["tests_executed"])
        self.assertEqual((result["passed"], result["failed"], result["total"]), (0, 0, 0))

    def test_failed_command_surfaces_nonzero_in_mcp_and_cli(self):
        self.configure(self.script("import sys\nprint('assertion failed', file=sys.stderr)\nsys.exit(7)\n"))
        wrapped, result = self.call(framework="command")
        self.assertTrue(wrapped["isError"])
        self.assertEqual((result["status"], result["exit_code"]), ("failed", 7))
        self.assertEqual(result["failed"], 0)  # No invented per-test failure count.
        cli = subprocess.run([sys.executable, str(ROOT / "scripts/qa.py"), "--workspace",
                              str(self.project), "--tool", "run_tests"],
                             capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(cli.returncode, 1, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["exit_code"], 7)

    def test_relative_executable_resolves_from_selected_project(self):
        command = self.script("print('relative runner executed')\n")
        relative_executable = os.path.relpath(sys.executable, self.project)
        self.assertTrue((self.project / relative_executable).is_file())
        self.configure([relative_executable, *command[1:]])
        wrapped, result = self.call()
        self.assertFalse(wrapped["isError"], result)
        self.assertEqual(result["stdout"].strip(), "relative runner executed")
        self.assertEqual(Path(result["command"][0]), Path(sys.executable).resolve())

        # Keep explicit ./ paths project-relative too (Path.parent normalizes them).
        self.configure(["./local-runner", "argument"])
        with patch("qa_server.adapters.command_adapter.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, "ok", "")) as run:
            self.call()
        self.assertEqual(run.call_args.args[0][0], str(self.project / "local-runner"))

    def test_missing_executable_and_missing_configuration_are_unavailable(self):
        self.configure(["maker-test-command-that-does-not-exist"])
        wrapped, result = self.call()
        self.assertTrue(wrapped["isError"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["tests_executed"], 0)
        (self.project / "qa-config.yaml").write_text('test:\n  framework: command\n', encoding="utf-8")
        wrapped, result = self.call()
        self.assertTrue(wrapped["isError"])
        self.assertEqual(result["code"], "INVALID_TEST_COMMAND")

    def test_invalid_command_configuration_does_not_fall_back(self):
        for command in (None, "lua tests.lua", [], [""], ["lua", 1], ["lua", "bad\0arg"]):
            with self.subTest(command=command):
                self.configure(command)
                with self.assertRaises(ValueError):
                    load_config(working_dir=str(self.project), use_cache=False)

    def test_timeout_preserves_output_and_is_not_success(self):
        self.configure(self.script("import time\nprint('started', flush=True)\ntime.sleep(30)\n"), timeout_seconds=1)
        wrapped, result = self.call()
        self.assertTrue(wrapped["isError"])
        self.assertEqual(result["status"], "timed_out")
        self.assertIn("started", result["stdout"])
        self.assertIsNone(result["exit_code"])

    def test_explicit_builtin_override_and_next_call_uses_project_command(self):
        self.configure(self.script("print('project command')\n"))
        (self.project / "test_sample.py").write_text(
            "import unittest\nclass Sample(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n",
            encoding="utf-8")
        result = run_tests_handler({"working_dir": str(self.project), "framework": "unittest"})
        self.assertEqual(result["passed"], 1, result)
        self.assertNotIn("result_kind", result)
        _, result = self.call()
        self.assertEqual(result["stdout"].strip(), "project command")

    def test_coverage_and_regressions_do_not_execute_or_replace_baseline(self):
        self.configure(self.script("raise AssertionError('must not execute')\n"))
        baseline = self.project / "baseline.json"
        baseline.write_text('{"tests":{"existing":"PASS"}}', encoding="utf-8")
        before = baseline.read_bytes()
        with patch("subprocess.run") as run:
            coverage = get_coverage_handler({"working_dir": str(self.project)})
            explicit_coverage = get_coverage_handler({"working_dir": str(self.project), "framework": "command"})
            regression = check_regressions_handler({"working_dir": str(self.project),
                                                    "baseline": "baseline.json", "update_baseline": True})
        run.assert_not_called()
        self.assertEqual(coverage["status"], "unavailable")
        self.assertEqual(explicit_coverage, coverage)
        self.assertIsNone(coverage["percentage"])
        self.assertEqual(regression["status"], "unavailable")
        self.assertEqual(baseline.read_bytes(), before)
        for result in (coverage, explicit_coverage, regression):
            for stage in ({"stage_name": "unavailable", "passed": 0, "failed": 0, **result},
                          {"stage_name": "unavailable", "passed": 0, "failed": 0, "details": result}):
                report = aggregate_qa_report_handler({"stage_results": [stage]})
                self.assertEqual(report["overall_status"], "FAIL")
                self.assertIsNone(report["summary"]["pass_rate"])
                self.assertEqual(report["stages"][0]["status"], "unavailable")
                report = aggregate_qa_report_handler({"stage_results": [
                    {"stage_name": "other", "passed": 2, "failed": 0}, stage]})
                self.assertEqual(report["overall_status"], "FAIL")

    def test_unsupported_filters_are_not_silently_ignored(self):
        self.configure(self.script("raise AssertionError('must not execute')\n"))
        wrapped, result = self.call(pattern="some_tests*")
        self.assertTrue(wrapped["isError"])
        self.assertEqual(result["code"], "UNSUPPORTED_COMMAND_OPTIONS")

    def test_hooks_and_extra_arguments(self):
        self.configure(self.script("import sys\nprint(sys.argv[1])\n"), extra_args=["extra"])
        with patch("qa_server.adapters.command_adapter.CommandAdapter._run_hooks", return_value=None) as hooks:
            _, result = self.call()
        self.assertEqual(result["stdout"].strip(), "extra")
        self.assertEqual([call.args[1] for call in hooks.call_args_list], ["pre", "post"])
        with patch("qa_server.adapters.command_adapter.CommandAdapter._run_hooks",
                   side_effect=[None, "cleanup failed"]):
            wrapped, result = self.call()
        self.assertTrue(wrapped["isError"])
        self.assertEqual(result["code"], "COMMAND_POST_HOOK_FAILED")

    def test_zero_test_command_never_aggregates_as_test_pass(self):
        self.configure(self.script("print('0 tests collected')\n"))
        _, result = self.call()
        for stage in ({"stage_name": "lua", **result},
                      {"stage_name": "lua", "passed": 0, "failed": 0, "details": result}):
            report = aggregate_qa_report_handler({"stage_results": [stage]})
            self.assertEqual(report["overall_status"], "PARTIAL")
            self.assertIsNone(report["summary"]["pass_rate"])
        report = aggregate_qa_report_handler({"stage_results": [
            {"stage_name": "lua", **result, "status": "failed"}]})
        self.assertEqual(report["overall_status"], "FAIL")

    @unittest.skipUnless(shutil.which("lua"), "Lua is not installed")
    def test_real_lua_command_passes_and_fails(self):
        self.configure([shutil.which("lua"), "suite.lua"])
        for expected, status in ((2, "succeeded"), (3, "failed")):
            (self.project / "suite.lua").write_text(
                f"assert(1 + 1 == {expected}, 'addition assertion')\nprint('Lua assertion passed')\n",
                encoding="utf-8")
            wrapped, result = self.call()
            self.assertEqual(result["status"], status, result)
            self.assertEqual(wrapped["isError"], status != "succeeded")


if __name__ == "__main__":
    unittest.main()
