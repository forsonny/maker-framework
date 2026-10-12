"""Durable MAKER step state and file-copy checkpoints; no background scheduler."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import uuid


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def project_file(root, name):
    relative = Path(name)
    path = (root / relative).resolve()
    if relative.is_absolute() or not relative.parts or any(p in {"..", ".git", ".maker"} for p in relative.parts):
        raise ValueError(f"Use a project-relative file outside .git and .maker: {name}")
    path.relative_to(root)
    if path.is_dir():
        raise ValueError(f"Checkpoint individual files, not directories: {name}")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def load(root):
    pointer = root / ".maker" / "current.json"
    if not pointer.exists():
        return None, None
    run_id = json.loads(pointer.read_text(encoding="utf-8"))["run_id"]
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise ValueError("Invalid run ID")
    path = root / ".maker" / "runs" / run_id / "state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    if state["workspace"] != str(root):
        raise ValueError("State belongs to a different workspace")
    return path, state


def reference_path(root, value):
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError("Reference paths must be nonempty strings or Paths")
    # Locators only: references do not grant write ownership or require existing files.
    return str((root / value).resolve())


def references(root, values):
    if not isinstance(values, dict) or any(
        not isinstance(name, str) or not name.strip() or not isinstance(value, str) or not value.strip()
        for name, value in values.items()
    ):
        raise ValueError("References must map nonempty string names to nonempty string paths")
    return {name: reference_path(root, value) for name, value in values.items()}


def execute(root, command, plan=None, step_id=None, evidence=None, plan_ref=None, evidence_refs=None):
    root = Path(root).resolve(strict=True)
    if plan_ref is not None:
        if command != "init":
            raise ValueError("Plan references apply only to init")
        plan_ref = reference_path(root, plan_ref)
    if evidence_refs is not None:
        if command not in {"finish", "complete"}:
            raise ValueError("Evidence references apply only to finish or complete")
        evidence_refs = references(root, evidence_refs)
    path, state = load(root)
    if command == "status":
        return state or {"status": "NOT_STARTED"}
    if command == "init":
        if state and state["status"] != "COMPLETED":
            raise ValueError("An unfinished run exists; resume it first")
        if not plan or not isinstance(plan.get("task"), str) or not plan["task"].strip() or not plan.get("steps"):
            raise ValueError("Plan needs a task and nonempty steps")
        ids = set()
        steps = []
        for item in plan["steps"]:
            sid = item.get("id", "")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", sid) or sid in ids:
                raise ValueError("Step IDs must be unique letters, digits, hyphens or underscores")
            ids.add(sid)
            if not item.get("action") or not isinstance(item.get("files"), list):
                raise ValueError("Each step needs an action and a files list")
            for name in item["files"]:
                project_file(root, name)
            step = {"id": sid, "action": item["action"], "files": list(dict.fromkeys(item["files"])), "status": "PENDING"}
            if "context_refs" in item:
                step["context_refs"] = references(root, item["context_refs"])
            steps.append(step)
        context_refs = references(root, plan["context_refs"]) if "context_refs" in plan else None
        run_id = uuid.uuid4().hex
        path = root / ".maker" / "runs" / run_id / "state.json"
        state = {"run_id": run_id, "task": plan["task"], "workspace": str(root), "status": "IN_PROGRESS",
                 "created_at": datetime.now(timezone.utc).isoformat(), "steps": steps}
        if plan_ref is not None:
            state["plan_ref"] = plan_ref
        if context_refs is not None:
            state["context_refs"] = context_refs
        save(path, state)
        save(root / ".maker" / "current.json", {"run_id": run_id})
        return state
    if not state:
        raise ValueError("No MAKER run exists")
    if command == "complete":
        if not evidence or any(s["status"] != "COMPLETED" for s in state["steps"]):
            raise ValueError("Complete every step and provide final review evidence first")
        state["status"] = "COMPLETED"
        state["review"] = evidence
        if evidence_refs is not None:
            state["review_refs"] = evidence_refs
    elif command == "pause":
        state["status"] = "PAUSED"
    else:
        step = next((s for s in state["steps"] if s["id"] == step_id), None)
        if not step:
            raise ValueError("Unknown step")
        snapshot = path.parent / "snapshots" / step_id
        if command == "start":
            previous = state["steps"][:state["steps"].index(step)]
            if any(s["status"] != "COMPLETED" for s in previous) or step["status"] != "PENDING":
                raise ValueError("Start the next pending step; inspect interrupted steps before retrying")
            # Validate every path before making a snapshot. Checkpoint creation never changes the worktree.
            sources = [(name, project_file(root, name)) for name in step["files"]]
            before = {}
            for name, source in sources:
                before[name] = digest(source)
                if source.exists():
                    dest = snapshot / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
            step["before"] = before
            step["status"] = "IN_PROGRESS"
            state["status"] = "IN_PROGRESS"
        elif command == "finish":
            if step["status"] != "IN_PROGRESS" or not evidence:
                raise ValueError("Finish requires an in-progress step and verification evidence")
            step["evidence"] = evidence
            if evidence_refs is not None:
                step["evidence_refs"] = evidence_refs
            step["after"] = {name: digest(project_file(root, name)) for name in step["files"]}
            step["status"] = "COMPLETED"
        elif command == "restore":
            if step["status"] != "IN_PROGRESS":
                raise ValueError("Only the interrupted active step can be restored")
            destinations = [(name, project_file(root, name)) for name in step["files"]]
            for name, dest in destinations:
                before = step["before"][name]
                if before is not None and digest(snapshot / name) != before:
                    raise ValueError(f"Snapshot missing or changed: {name}")
            for name, dest in destinations:
                if step["before"][name] is None:
                    if dest.exists():
                        dest.unlink()
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(snapshot / name, dest)
            step["status"] = "PENDING"
            state["status"] = "PAUSED"
        else:
            raise ValueError("Unknown command")
    save(path, state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "status", "start", "finish", "pause", "restore", "complete"])
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--step")
    parser.add_argument("--evidence")
    parser.add_argument("--evidence-ref", action="append", help="File locator name=path for finish or complete; repeat for multiple reports")
    parser.add_argument("--confirm-restore", action="store_true", help="Confirm overwriting the listed step files from its snapshot")
    args = parser.parse_args()
    if args.command == "restore" and not args.confirm_restore:
        parser.error("Inspect the current files first; restore requires --confirm-restore")
    try:
        evidence_refs = None
        if args.evidence_ref is not None:
            evidence_refs = {}
            for value in args.evidence_ref:
                name, separator, path = value.partition("=")
                if not separator or name in evidence_refs:
                    raise ValueError("Use unique --evidence-ref name=path entries")
                evidence_refs[name] = path
        plan = json.loads(args.plan.read_text(encoding="utf-8")) if args.plan else None
        plan_ref = args.plan.resolve() if args.command == "init" and args.plan else None
        print(json.dumps(execute(args.workspace, args.command, plan, args.step, args.evidence,
                                 plan_ref=plan_ref, evidence_refs=evidence_refs), indent=2))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"MAKER: {exc}\n")


if __name__ == "__main__":
    main()
