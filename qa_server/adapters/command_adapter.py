"""Run a project's command without inventing individual test results."""
import os
import subprocess
import time

from .base import BaseAdapter
from ..config import TestConfig


class CommandAdapter(BaseAdapter):
    name = "command"

    def detect(self):
        # Selected only by explicit project configuration, never file guessing.
        return False

    def supports_coverage(self):
        return False

    def get_coverage(self, config=None, verbose=False):
        return {"status": "unavailable", "code": "COMMAND_COVERAGE_UNAVAILABLE",
                "message": "Project commands do not provide structured coverage results.",
                "tests_executed": 0, "percentage": None,
                "uncovered_lines": [], "meets_threshold": False}

    def run_tests(self, pattern=None, config=None, verbose=False):
        config = config or TestConfig()
        started = time.monotonic()
        result = {
            "result_kind": "command", "status": "unavailable",
            "command": config.command, "exit_code": None,
            "stdout": "", "stderr": "", "duration_ms": 0,
            "test_counts_known": False, "tests_executed": 0,
            "passed": 0, "failed": 0, "total": 0, "failures": [], "passed_names": [],
            "message": "Individual test counts are unknown; command success alone does not prove tests ran.",
        }

        def finish(status, code=None, message=None):
            result["status"] = status
            result["duration_ms"] = int((time.monotonic() - started) * 1000)
            if code:
                result["code"] = code
            if message:
                result["message"] = message
            return result

        command = config.command
        if (not isinstance(command, list) or not command
                or any(not isinstance(arg, str) or "\0" in arg for arg in command)
                or not command[0].strip()):
            return finish("unavailable", "INVALID_TEST_COMMAND",
                          "Configure test.command as a nonempty executable/argument list.")
        if pattern or config.patterns or config.parallel:
            return finish("unavailable", "UNSUPPORTED_COMMAND_OPTIONS",
                          "Put filtering and parallel options in test.command or test.extra_args.")

        hook_error = self._run_hooks(config.pre_hooks, "pre")
        if hook_error:
            return finish("error", "COMMAND_PRE_HOOK_FAILED", hook_error)

        result["command"] = [*command, *config.extra_args]
        # Windows resolves the executable before applying subprocess cwd.
        if not os.path.isabs(command[0]) and os.path.dirname(command[0]):
            result["command"][0] = str((self.working_dir / command[0]).resolve())
        try:
            completed = subprocess.run(
                result["command"], cwd=str(self.working_dir), shell=False,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=config.timeout_seconds,
            )
            result.update(exit_code=completed.returncode, stdout=completed.stdout,
                          stderr=completed.stderr, tests_executed=None)
            finish("succeeded" if completed.returncode == 0 else "failed")
        except subprocess.TimeoutExpired as exc:
            # TimeoutExpired can carry bytes even when text=True.
            for field, output in (("stdout", exc.stdout), ("stderr", exc.stderr)):
                result[field] = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output or ""
            result["tests_executed"] = None
            finish("timed_out", "TEST_COMMAND_TIMEOUT", "Project test command exceeded its timeout.")
        except OSError as exc:
            finish("unavailable", "TEST_COMMAND_UNAVAILABLE", str(exc))

        hook_error = self._run_hooks(config.post_hooks, "post")
        if hook_error:
            return finish("error", "COMMAND_POST_HOOK_FAILED", hook_error)
        return finish(result["status"])
