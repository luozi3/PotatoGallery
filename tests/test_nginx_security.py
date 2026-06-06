from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _nginx_conf() -> str:
    return (ROOT / "deploy" / "nginx" / "potato_gallery.conf").read_text(encoding="utf-8")


def test_nginx_uses_cloudflare_real_ip_and_tunnel_trust():
    conf = _nginx_conf()
    assert "real_ip_header CF-Connecting-IP;" in conf
    assert "real_ip_recursive on;" in conf
    assert "set_real_ip_from 173.245.48.0/20;" in conf
    assert "set_real_ip_from 2a06:98c0::/29;" in conf
    assert "set_real_ip_from 127.0.0.1;" in conf
    assert "set_real_ip_from ::1;" in conf


def test_nginx_limits_login_locations_without_limiting_all_admin_api():
    conf = _nginx_conf()
    assert "limit_req_zone $binary_remote_addr zone=gallery_user_login" in conf
    assert "limit_req_zone $binary_remote_addr zone=gallery_register" in conf
    assert "location = /auth/login" in conf
    assert "limit_req zone=gallery_user_login burst=10 nodelay;" in conf
    assert "location = /upload/admin/login" not in conf
    assert "gallery_admin_login" not in conf
    admin_location_start = conf.index("location ~ ^/(api|upload/admin)/")
    admin_location_end = conf.index("location ~ ^/auth/(logout|me)$")
    assert "limit_req zone=" not in conf[admin_location_start:admin_location_end]


def test_nginx_forwards_normalized_ip_and_cloudflare_proto():
    conf = _nginx_conf()
    assert "map $http_x_forwarded_proto $gallery_forwarded_proto" in conf
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in conf
    assert "proxy_set_header X-Real-IP $remote_addr;" in conf
    assert "proxy_set_header X-Forwarded-Proto $gallery_forwarded_proto;" in conf
