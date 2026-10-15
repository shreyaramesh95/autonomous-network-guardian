from __future__ import annotations

import os
import tempfile

import pytest

from ang import create_app
from ang.config import TestConfig
from ang.database.db import connection, init_db


def config_dict(**overrides) -> dict:
    d = {k: getattr(TestConfig, k) for k in dir(TestConfig) if k.isupper()}
    d.update(overrides)
    return d


@pytest.fixture()
def db_path():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    init_db(path, seed=True)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture()
def cfg(db_path):
    return config_dict(DATABASE=db_path)


@pytest.fixture()
def app(db_path):
    app = create_app(TestConfig, DATABASE=db_path, START_MONITORING=False,
                     AUTO_INIT_DB=False)
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def conn(db_path):
    with connection(db_path) as c:
        yield c
