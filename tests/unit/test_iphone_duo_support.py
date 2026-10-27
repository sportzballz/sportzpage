from pathlib import Path


TEMPLATES = (
    "index.html.j2",
    "football.html.j2",
    "ncaaf.html.j2",
    "nhl.html.j2",
    "nba.html.j2",
)


def test_all_editions_opt_into_edge_to_edge_viewport() -> None:
    for name in TEMPLATES:
        template = (Path("templates") / name).read_text(encoding="utf-8")
        assert "viewport-fit=cover" in template


def test_newspaper_respects_asymmetric_safe_areas() -> None:
    stylesheet = Path("static/css/daily-sports-page.css").read_text(encoding="utf-8")
    assert "env(safe-area-inset-left)" in stylesheet
    assert "env(safe-area-inset-right)" in stylesheet
    assert "env(safe-area-inset-bottom)" in stylesheet


def test_native_shell_has_no_fixed_screen_assumptions() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in Path("ios/TDSPApp").glob("*.swift")
    )
    assert "UIScreen.main" not in sources
    assert "interfaceOrientation" not in sources
