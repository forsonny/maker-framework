"""Exercise resumable state, non-destructive snapshots and bounded restore."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.maker_state import execute


class StateChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="maker state ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = {"task": "Example", "steps": [
            {"id": "one", "action": "Edit files", "files": ["existing.txt", "new.txt"]},
            {"id": "two", "action": "Verify", "files": []}]}
        (self.root / "existing.txt").write_text("user changes")

    def test_resume_and_final_review_gate(self):
        self.assertEqual(execute(self.root, "status")["status"], "NOT_STARTED")
        execute(self.root, "init", plan=self.plan)
        self.assertNotIn("plan_ref", execute(self.root, "status"))
        self.assertNotIn("context_refs", execute(self.root, "status"))
        with self.assertRaises(ValueError):
            execute(self.root, "init", plan=self.plan)
        with self.assertRaises(ValueError):
            execute(self.root, "start", step_id="two")
        execute(self.root, "start", step_id="one")
        self.assertEqual((self.root / "existing.txt").read_text(), "user changes")
        (self.root / "existing.txt").write_text("implemented")
        execute(self.root, "pause")
        self.assertEqual(execute(self.root, "status")["steps"][0]["status"], "IN_PROGRESS")
        execute(self.root, "finish", step_id="one", evidence="Checked requested output")
        with self.assertRaises(ValueError):
            execute(self.root, "complete", evidence="Premature review")
        execute(self.root, "start", step_id="two")
        execute(self.root, "finish", step_id="two", evidence="Checks passed")
        result = execute(self.root, "complete", evidence="Independent review complete")
        self.assertEqual(result["status"], "COMPLETED")
        execute(self.root, "init", plan=self.plan)
        self.assertEqual(len(list((self.root / ".maker/runs").iterdir())), 2)

    def test_restore_preserves_unrelated_files(self):
        execute(self.root, "init", plan=self.plan)
        execute(self.root, "start", step_id="one")
        (self.root / "existing.txt").write_text("failed edit")
        (self.root / "new.txt").write_text("new file")
        (self.root / "unrelated.txt").write_text("keep")
        execute(self.root, "restore", step_id="one")
        self.assertEqual((self.root / "existing.txt").read_text(), "user changes")
        self.assertFalse((self.root / "new.txt").exists())
        self.assertEqual((self.root / "unrelated.txt").read_text(), "keep")
        self.assertEqual(execute(self.root, "status")["steps"][0]["status"], "PENDING")

    def test_restore_rejects_corrupt_snapshot_before_writing(self):
        state = execute(self.root, "init", plan=self.plan)
        execute(self.root, "start", step_id="one")
        (self.root / "existing.txt").write_text("new content")
        snapshot = self.root / ".maker/runs" / state["run_id"] / "snapshots/one/existing.txt"
        snapshot.write_text("corrupt")
        with self.assertRaises(ValueError):
            execute(self.root, "restore", step_id="one")
        self.assertEqual((self.root / "existing.txt").read_text(), "new content")

    def test_rejects_paths_outside_project(self):
        for name in ["../outside.txt", ".git/config", ".maker/current.json"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                execute(self.root, "init", plan={"task": "Invalid", "steps": [{"id": "one", "action": "Edit", "files": [name]}]})

    def test_context_and_evidence_references_survive_resume(self):
        external = self.root.parent / "planned external review.md"
        self.plan["context_refs"] = {"brief": "accepted brief.md", "acceptance": str(external)}
        self.plan["steps"][0]["context_refs"] = {"contract": "contracts/one.md"}
        execute(self.root, "init", plan=self.plan, plan_ref="accepted plan.json")
        execute(self.root, "start", step_id="one")
        with self.assertRaises(ValueError):
            execute(self.root, "finish", step_id="one", evidence_refs={"solver": "solver.md"})
        execute(self.root, "finish", step_id="one", evidence="Verified output",
                evidence_refs={"solver": "reports/solver.md", "validator": str(external)})
        execute(self.root, "pause")
        resumed = execute(self.root, "status")
        self.assertEqual(resumed["plan_ref"], str(self.root / "accepted plan.json"))
        self.assertEqual(resumed["context_refs"], {"brief": str(self.root / "accepted brief.md"), "acceptance": str(external)})
        self.assertEqual(resumed["steps"][0]["context_refs"], {"contract": str(self.root / "contracts/one.md")})
        self.assertEqual(resumed["steps"][0]["evidence_refs"], {"solver": str(self.root / "reports/solver.md"), "validator": str(external)})
        self.assertEqual(resumed["steps"][0]["evidence"], "Verified output")
        self.assertEqual((self.root / "existing.txt").read_text(), "user changes")
        self.assertFalse((self.root / "accepted brief.md").exists())
        execute(self.root, "start", step_id="two")
        execute(self.root, "finish", step_id="two", evidence="Checked")
        with self.assertRaises(ValueError):
            execute(self.root, "complete", evidence_refs={"auditor": "auditor.md"})
        execute(self.root, "complete", evidence="Final review", evidence_refs={"auditor": "reports/auditor.md"})
        self.assertEqual(execute(self.root, "status")["review_refs"], {"auditor": str(self.root / "reports/auditor.md")})

    def test_invalid_reference_metadata_does_not_mutate_state(self):
        invalid = [None, [], "brief.md", {"": "brief.md"}, {"brief": " "}, {"brief": 3}, {3: "brief.md"}]
        for value in invalid:
            for target in [self.plan, self.plan["steps"][0]]:
                with self.subTest(value=value, target=target):
                    target["context_refs"] = value
                    with self.assertRaises(ValueError):
                        execute(self.root, "init", plan=self.plan)
                    self.assertFalse((self.root / ".maker").exists())
                    del target["context_refs"]
        with self.assertRaises(ValueError):
            execute(self.root, "init", plan=self.plan, plan_ref=3)
        state = execute(self.root, "init", plan=self.plan)
        execute(self.root, "start", step_id="one")
        state_path = self.root / ".maker/runs" / state["run_id"] / "state.json"
        before = state_path.read_bytes()
        for value in invalid[1:]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                execute(self.root, "finish", step_id="one", evidence="Checked", evidence_refs=value)
            self.assertEqual(state_path.read_bytes(), before)
        with self.assertRaises(ValueError):
            execute(self.root, "pause", evidence_refs={"solver": "solver.md"})
        self.assertEqual(state_path.read_bytes(), before)
        execute(self.root, "finish", step_id="one", evidence="Checked")
        execute(self.root, "start", step_id="two")
        execute(self.root, "finish", step_id="two", evidence="Checked")
        before = state_path.read_bytes()
        with self.assertRaises(ValueError):
            execute(self.root, "complete", evidence="Final review", evidence_refs={"review": ""})
        self.assertEqual(state_path.read_bytes(), before)

    def test_cli_reference_paths_resolve_from_workspace_and_plan_cwd(self):
        caller_temp = tempfile.TemporaryDirectory(prefix="maker caller ")
        self.addCleanup(caller_temp.cleanup)
        caller = Path(caller_temp.name)
        script = Path(__file__).resolve().parents[1] / "scripts/maker_state.py"
        self.plan["context_refs"] = {"brief": "accepted brief.md", "criteria": str(caller / "criteria.md")}
        (caller / "accepted plan.json").write_text(json.dumps(self.plan), encoding="utf-8")

        def cli(command, *args):
            return subprocess.run([sys.executable, str(script), command, "--workspace", str(self.root), *args],
                                  cwd=caller, capture_output=True, text=True)

        init = cli("init", "--plan", "accepted plan.json")
        self.assertEqual(init.returncode, 0, init.stderr)
        self.assertEqual(json.loads(init.stdout)["plan_ref"], str(caller / "accepted plan.json"))
        self.assertEqual(cli("start", "--step", "one").returncode, 0)
        before = execute(self.root, "status")
        for refs in [("broken",), ("solver=one.md", "solver=two.md"), ("=one.md",), ("solver=",)]:
            args = [arg for ref in refs for arg in ("--evidence-ref", ref)]
            result = cli("finish", "--step", "one", "--evidence", "Checked", *args)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(execute(self.root, "status"), before)
        finish = cli("finish", "--step", "one", "--evidence", "Checked", "--evidence-ref", "solver=solver report.md",
                     "--evidence-ref", "validator=" + str(caller / "validator report.md"))
        self.assertEqual(finish.returncode, 0, finish.stderr)
        self.assertEqual(cli("start", "--step", "two").returncode, 0)
        self.assertEqual(cli("finish", "--step", "two", "--evidence", "Checked").returncode, 0)
        complete = cli("complete", "--evidence", "Final review", "--evidence-ref", "auditor=final review.md")
        self.assertEqual(complete.returncode, 0, complete.stderr)
        status = cli("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        saved = json.loads(status.stdout)
        self.assertEqual(saved["context_refs"], {"brief": str(self.root / "accepted brief.md"), "criteria": str(caller / "criteria.md")})
        self.assertEqual(saved["steps"][0]["evidence_refs"], {"solver": str(self.root / "solver report.md"), "validator": str(caller / "validator report.md")})
        self.assertEqual(saved["review_refs"], {"auditor": str(self.root / "final review.md")})


if __name__ == "__main__":
    unittest.main()
