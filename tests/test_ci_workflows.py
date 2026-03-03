"""Tests to validate GitHub Actions workflow YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOWS_DIR = Path(__file__).parent.parent / ".github" / "workflows"


class TestCIWorkflows:
    def test_workflow_files_exist(self):
        """Ensure there is at least one workflow file."""
        workflow_files = list(WORKFLOWS_DIR.glob("*.yml"))
        assert len(workflow_files) > 0, "No workflow files found in .github/workflows/"

    def test_all_workflows_are_valid_yaml(self):
        """All workflow YAML files must parse without errors."""
        workflow_files = list(WORKFLOWS_DIR.glob("*.yml"))
        for workflow_file in workflow_files:
            content = workflow_file.read_text(encoding="utf-8")
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as exc:
                raise AssertionError(
                    f"Invalid YAML in {workflow_file.name}: {exc}"
                ) from exc

    def test_build_workflow_has_required_jobs(self):
        """build.yml must define expected top-level jobs."""
        build_yml = WORKFLOWS_DIR / "build.yml"
        assert build_yml.exists(), "build.yml not found"
        data = yaml.safe_load(build_yml.read_text(encoding="utf-8"))
        jobs = data.get("jobs", {})
        required_jobs = {"lint-and-test", "build-linux", "build-macos", "build-windows"}
        missing = required_jobs - set(jobs)
        assert not missing, f"build.yml is missing expected jobs: {missing}"

    def test_build_workflow_triggers(self):
        """build.yml must define push, pull_request, and workflow_dispatch triggers."""
        build_yml = WORKFLOWS_DIR / "build.yml"
        data = yaml.safe_load(build_yml.read_text(encoding="utf-8"))
        # PyYAML 1.1 parses bare `on` as boolean True; handle both key forms.
        triggers = set((data.get(True) or data.get("on") or {}).keys())
        required_triggers = {"push", "pull_request", "workflow_dispatch"}
        missing = required_triggers - triggers
        assert not missing, f"build.yml is missing expected triggers: {missing}"
