"""
Backend tests. They need a real Postgres (the models use Postgres UUIDs):

    createdb tweezers_test
    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/tweezers_test pytest

Without TEST_DATABASE_URL every test is skipped. The test database is wiped
and rebuilt from the Alembic migrations once per run.
"""
import itertools
import os
import sys

import pytest

URL = os.getenv("TEST_DATABASE_URL")
if not URL:
    collect_ignore_glob = ["test_*.py"]  # nothing to run without a database
else:
    os.environ["DATABASE_URL"] = URL
    os.environ["AUTH_DEV_BYPASS"] = "true"
    os.environ["PAYMENTS_ENABLED"] = "true"
    os.environ["ANTHROPIC_API_KEY"] = ""
    os.environ["FIREBASE_PROJECT_ID"] = "test-project"
    os.environ["CASHFREE_CLIENT_ID"] = "test-id"
    os.environ["CASHFREE_CLIENT_SECRET"] = "test-secret"
    os.environ["RENDER_SERVICE_URL"] = ""
    os.environ["RENDER_SECRET"] = "render-secret"
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def pytest_report_header(config):
    return None if URL else "TEST_DATABASE_URL not set: backend tests skipped"


@pytest.fixture(scope="session")
def client():
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient

    from app.database import Base, engine
    from app.main import app

    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    cfg = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic"))
    command.upgrade(cfg, "head")

    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    db.add(models.Template(name="T1", category="c", mood_tags=["romantic"]))
    db.add(models.MusicTrack(title="M1", audio_file_url="/static/music/soft_piano_love.mp3", mood_tags=["romantic"]))
    db.add(models.CreditPack(label="Pack", credits=50, price_inr=49))
    db.commit()
    db.close()
    return TestClient(app)


_counter = itertools.count(1)  # unique phones across the whole run


@pytest.fixture()
def make_user(client):
    """Returns (user_id, auth_headers) for a fresh dev user."""
    def make(credits: int = 0):
        u = client.post("/auth/signup", json={"phone": f"+9190{next(_counter):08d}"}).json()
        if credits:
            from app import models
            from app.database import SessionLocal

            db = SessionLocal()
            db.query(models.User).filter(models.User.id == u["id"]).update({"credits_balance": credits})
            db.commit()
            db.close()
        return u["id"], {"Authorization": f"Bearer dev:{u['id']}"}

    return make
