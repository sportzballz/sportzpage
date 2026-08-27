from pathlib import Path


WORKFLOW = Path(".github/workflows/deploy.yml")


def test_deploy_retries_hourly_from_3am_eastern() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'cron: "17 3-23 * * *"' in workflow
    assert 'timezone: "America/New_York"' in workflow


def test_scheduled_retry_skips_after_todays_edition_is_live() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "publication-check:" in workflow
    assert "PUBLISHED_DATE" in workflow
    assert 'echo "should_publish=false" >> "$GITHUB_OUTPUT"' in workflow
    assert "needs: publication-check" in workflow
    assert "needs.publication-check.outputs.should_publish == 'true'" in workflow


def test_push_and_manual_runs_still_publish() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'if [[ "$EVENT_NAME" != "schedule" ]]' in workflow
    assert 'echo "should_publish=true" >> "$GITHUB_OUTPUT"' in workflow
