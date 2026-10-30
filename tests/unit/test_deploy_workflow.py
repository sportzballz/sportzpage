from pathlib import Path

WORKFLOW = Path(".github/workflows/deploy.yml")


def test_deploy_retries_hourly_from_3am_eastern() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'cron: "17 3-23 * * *"' in workflow
    assert 'timezone: "America/New_York"' in workflow


def test_scheduled_retry_skips_only_after_all_editions_are_live() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "publication-check:" in workflow
    assert "MISSING_EDITIONS" in workflow
    assert "current/football/edition.json" in workflow
    assert "current/ncaaf/edition.json" in workflow
    assert "current/nhl/edition.json" in workflow
    assert "current/nba/edition.json" in workflow
    assert "GENERATED_DATE" in workflow
    assert 'echo "should_publish=false" >> "$GITHUB_OUTPUT"' in workflow
    assert "needs: publication-check" in workflow
    assert "needs.publication-check.outputs.should_publish == 'true'" in workflow


def test_push_and_manual_runs_still_publish() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'if [[ "$EVENT_NAME" != "schedule" ]]' in workflow
    assert 'echo "should_publish=true" >> "$GITHUB_OUTPUT"' in workflow


def test_mlb_is_seasonal_and_does_not_block_offseason_publication() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "include_mlb: ${{ steps.publication.outputs.include_mlb }}" in workflow
    assert 'if [[ "$MONTH_DAY" > "02-29" && "$MONTH_DAY" < "10-30" ]]' in workflow
    assert 'if [[ "$NAME" == "MLB" && "$INCLUDE_MLB" != "true" ]]' in workflow
    assert "needs.publication-check.outputs.include_mlb" in workflow
    assert "python scripts/generate_market_editions.py --skip-baseball" in workflow
    assert "ASSEMBLE_ARGS+=(--exclude-mlb)" in workflow


def test_publish_date_is_separate_from_coverage_date() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'date -d \'yesterday\' +%F' in workflow
    assert 'publication_date=$(TZ=America/New_York date +%F)' in workflow
    assert '--edition-date "$PUBLICATION_DATE"' in workflow
    assert workflow.count('--publication-date "$PUBLICATION_DATE"') == 2
    assert 'src.nhl.generator --date "$PUBLICATION_DATE"' in workflow
    assert 'src.nba.generator --date "$PUBLICATION_DATE"' in workflow


def test_deploy_generates_and_assembles_nba() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "python -m src.nba.generator" in workflow
    assert "--nba-market-dir build/nba-markets" in workflow
    assert "/subscriber/current/nba/edition.json" in workflow
