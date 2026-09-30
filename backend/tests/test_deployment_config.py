import importlib
import ssl

import pytest
from sqlalchemy import create_engine
from app.config import get_settings


@pytest.mark.parametrize("scheme", ["redis", "rediss"])
def test_redis_transport_tls_and_existing_task_limits(monkeypatch, scheme):
    from app.tasks import celery_app as module

    monkeypatch.setenv("REDIS_URL", f"{scheme}://default:dummy-token@redis.example.com:6379/0")
    original = module.celery_app
    get_settings.cache_clear()
    try:
        importlib.reload(module)
        app = module.celery_app
        assert app.conf.broker_url == get_settings().redis_url
        assert app.conf.result_backend == get_settings().redis_url
        assert (app.conf.task_soft_time_limit, app.conf.task_time_limit) == (270, 300)
        assert app.conf.task_ignore_result is True
        if scheme == "rediss":
            assert app.conf.broker_use_ssl["ssl_cert_reqs"] == ssl.CERT_REQUIRED
            assert app.conf.broker_use_ssl["ssl_check_hostname"] is True
            assert app.backend.connparams["ssl_cert_reqs"] == ssl.CERT_REQUIRED
            assert app.backend.connparams["ssl_check_hostname"] is True
        else:
            assert not app.conf.broker_use_ssl
            assert not app.conf.redis_backend_use_ssl
        app.close()
    finally:
        get_settings.cache_clear()
        module.celery_app = original


def test_postgresql_psycopg_url_passes_tls_options_without_connecting():
    engine = create_engine("postgresql+psycopg://demo:encoded%40password@server.postgres.database.azure.com:5432/codesentry?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt")
    try:
        _, args = engine.dialect.create_connect_args(engine.url)
        assert args["password"] == "encoded@password"
        assert args["sslmode"] == "verify-full"
        assert args["sslrootcert"] == "/etc/ssl/certs/ca-certificates.crt"
    finally:
        engine.dispose()
