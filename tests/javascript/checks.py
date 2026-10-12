"""Real JavaScript adapter checks; run explicitly after npm ci in this folder."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from qa_server.tools.check_regressions import check_regressions_handler
from qa_server.tools.get_coverage import get_coverage_handler
from qa_server.tools.run_tests import run_tests_handler

ROOT = Path(__file__).resolve().parent


class JavaScriptAdapterChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for command in ("node", "npx"):
            if not shutil.which(command):
                raise RuntimeError(f"{command} is required for JavaScript adapter checks")
        versions = json.loads((ROOT / "package.json").read_text())["dependencies"]
        for package, version in versions.items():
            manifest = ROOT / "node_modules" / package / "package.json"
            binary = ROOT / "node_modules" / ".bin" / (package + (".cmd" if os.name == "nt" else ""))
            if not manifest.is_file() or not binary.is_file():
                raise RuntimeError(f"Missing {package}; run npm ci in {ROOT}")
            installed = json.loads(manifest.read_text())["version"]
            if installed != version:
                raise RuntimeError(f"Expected {package} {version}, found {installed}; run npm ci in {ROOT}")

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fixture-", dir=ROOT)
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)
        env = patch.dict(os.environ, {
            "QA_ALLOWED_PATHS": str(self.project),
            "npm_config_offline": "true",
            "npm_config_yes": "false",
        })
        env.start()
        self.addCleanup(env.stop)
        for name in ("QA_CONFIG_PATH", "MAKER_QA_WORKSPACE_MODE"):
            os.environ.pop(name, None)
        (self.project / "src").mkdir()
        (self.project / "src" / "add.js").write_text(
            "exports.add = (a,b) => a+b;\n"
            "exports.subtract = (a,b) => {\n  return a-b;\n};\n", encoding="utf-8")

    def arguments(self, **kwargs):
        return {"working_dir": str(self.project), "framework": self.framework, **kwargs}

    def write_sample(self, failing):
        expected = 3 if failing else 2
        if self.framework == "jest":
            content = ('const {add} = require("./src/add");\n'
                       'test("pass",()=>expect(add(1,1)).toBe(2));\n'
                       f'test("fail",()=>expect(add(1,1)).toBe({expected}));\n')
        else:
            content = ('const {add} = require("../src/add");\n'
                       'const assert = require("assert");\n'
                       'describe("sample",function(){\n'
                       '  it("pass",function(){assert.equal(add(1,1),2)});\n'
                       f'  it("fail",function(){{assert.equal(add(1,1),{expected})}});\n'
                       '});\n')
        self.sample.write_text(content, encoding="utf-8")

    def exercise_adapter(self, framework):
        self.framework = framework
        if framework == "jest":
            self.sample = self.project / "sample.test.js"
            selected = self.project / "selected.test.js"
            selected.write_text('test("selected",()=>expect(1+1).toBe(2));\n', encoding="utf-8")
            (self.project / "jest.config.cjs").write_text(
                'module.exports = {testMatch: ["**/*.test.js"], maxWorkers: 1};\n', encoding="utf-8")
            passing_names = {"pass", "selected"}
            failing_name = "fail"
        else:
            (self.project / "test").mkdir()
            self.sample = self.project / "test" / "sample.js"
            selected = self.project / "test" / "selected.js"
            selected.write_text('const assert = require("assert");\n'
                                'it("selected",function(){assert.equal(1+1,2)});\n', encoding="utf-8")
            passing_names = {"sample pass", "selected"}
            failing_name = "sample fail"
        (self.project / "package.json").write_text('{"private":true}\n', encoding="utf-8")
        (self.project / "qa-config.yaml").write_text(
            f"test:\n  framework: {framework}\n  timeout_seconds: 60\n"
            "coverage:\n  source_patterns: ['src/**/*.js']\n  timeout_seconds: 60\n", encoding="utf-8")

        self.write_sample(True)
        result = run_tests_handler(self.arguments())
        self.assertEqual((result["passed"], result["failed"], result["total"]), (2, 1, 3), result)
        self.assertEqual(set(result["passed_names"]), passing_names, result)
        self.assertEqual([failure["name"] for failure in result["failures"]], [failing_name], result)
        self.assertTrue(result["failures"][0]["message"], result)
        self.assertEqual(Path(result["failures"][0]["file"]).resolve(), self.sample.resolve())

        filtered = run_tests_handler(self.arguments(pattern="**/" + selected.name))
        self.assertEqual((filtered["passed"], filtered["failed"], filtered["total"]), (1, 0, 1), filtered)
        self.assertEqual(filtered["passed_names"], ["selected"], filtered)
        self.assertEqual(filtered["failures"], [], filtered)

        self.write_sample(False)
        baseline_args = self.arguments(baseline="qa-reports/baseline.json")
        initial = check_regressions_handler({**baseline_args, "update_baseline": True})
        self.assertEqual(initial["regressions"], [], initial)
        baseline_file = self.project / "qa-reports" / "baseline.json"
        baseline = json.loads(baseline_file.read_text())
        self.assertEqual(set(baseline["tests"]), passing_names | {failing_name}, baseline)
        self.assertTrue(all(test["status"] == "PASS" for test in baseline["tests"].values()), baseline)
        self.write_sample(True)
        regression = check_regressions_handler(baseline_args)
        self.assertEqual(len(regression["regressions"]), 1, regression)
        change = regression["regressions"][0]
        self.assertEqual((change["name"], change["previous_status"], change["current_status"]),
                         (failing_name, "PASS", "FAIL"), regression)
        self.assertEqual(regression["unchanged"], 2, regression)
        self.assertEqual(regression["missing_tests"], [], regression)
        self.assertEqual(json.loads(baseline_file.read_text()), baseline)

        covered = get_coverage_handler(self.arguments(threshold=50))
        self.assertGreater(covered["percentage"], 50, covered)
        self.assertLess(covered["percentage"], 100, covered)
        self.assertTrue(covered["meets_threshold"], covered)
        self.assertTrue(any(Path(line["file"]).resolve() == (self.project / "src" / "add.js").resolve()
                            for line in covered["uncovered_lines"]), covered)
        strict = get_coverage_handler(self.arguments(threshold=100))
        self.assertEqual(strict["percentage"], covered["percentage"], strict)
        self.assertFalse(strict["meets_threshold"], strict)

    def test_jest_adapter(self):
        self.exercise_adapter("jest")

    def test_mocha_adapter(self):
        self.exercise_adapter("mocha")


if __name__ == "__main__":
    unittest.main()
