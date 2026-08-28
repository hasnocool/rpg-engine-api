from pathlib import Path


def test_github_workflows_are_absent_or_empty() -> None:
    workflows = Path(".github/workflows")
    assert not workflows.exists() or not any(workflows.iterdir())
