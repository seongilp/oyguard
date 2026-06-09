import os
import tempfile

os.environ["OYGUARD_DEMO_MODE"] = "true"
os.environ["OYGUARD_WORK_DIR"] = tempfile.mkdtemp(prefix="oyguard-test-")

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app
from app.services.jobs import store


@pytest.fixture(autouse=True)
def _demo_settings():
    get_settings.cache_clear()
    s = get_settings()
    s.demo_mode = True
    # Reset the in-memory store between tests.
    store._jobs.clear()
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
