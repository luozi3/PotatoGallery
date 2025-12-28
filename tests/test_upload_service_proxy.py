from test_pipeline import seed_test_root, setup_env


def test_upload_service_main_trusts_proxy(monkeypatch, tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    upload_service = modules["app.upload_service"]
    called = {}

    def fake_serve(app, **kwargs):
        called.update(kwargs)

    monkeypatch.setattr(upload_service, "serve", fake_serve)
    monkeypatch.setenv("PORT", "5005")

    upload_service.main()

    assert called["trusted_proxy"] == "127.0.0.1"
    assert called["trusted_proxy_count"] == 1
    headers = called["trusted_proxy_headers"]
    assert "x-forwarded-proto" in headers
