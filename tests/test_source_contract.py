from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_source_is_reviewable_not_archive_only():
    for path in ["app.py", "locator/core.py", "web/share.html", "web/viewer.html", "render.yaml"]:
        assert (ROOT / path).is_file(), path
    assert not list(ROOT.glob("*.zip"))


def test_no_public_user_id_location_lookup_or_sms_token_fallback():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    share_js = (ROOT / "web/assets/share.js").read_text(encoding="utf-8")
    assert "/location/latest" not in source
    assert "user_id" not in source
    assert "sms:" not in share_js.lower()


def test_web_pages_do_not_auto_load_third_party_assets():
    for path in (ROOT / "web").glob("*.html"):
        html = path.read_text(encoding="utf-8").lower()
        assert '<script src="http' not in html
        assert '<link rel="stylesheet" href="http' not in html
    viewer = (ROOT / "web/assets/viewer.js").read_text(encoding="utf-8")
    assert "openstreetmap.org" in viewer
    assert "fetch(`https://" not in viewer


def test_render_deploy_is_health_checked_and_not_automatic():
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "healthCheckPath: /health" in render
    assert "autoDeploy: false" in render
