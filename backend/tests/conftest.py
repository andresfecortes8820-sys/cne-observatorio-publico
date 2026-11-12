import os
from pathlib import Path
import sys
import tempfile
import pytest
from cryptography.fernet import Fernet

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
test_directory=tempfile.TemporaryDirectory(prefix='cne-tests-')
test_path=Path(test_directory.name)/'test.db'
os.environ.update(DATABASE_URL=os.environ.get('TEST_DATABASE_URL','sqlite:///'+str(test_path).replace('\\','/')), JWT_SECRET='test-secret-'*5, TOKEN_KEY=Fernet.generate_key().decode(), ADMIN_PASSWORD='test-admin-password-1234', ADMIN_EMAIL='admin@test.local')
from app.db import Base,engine,Session
from app.main import app
from app.models import User
from app.security import password_hash,issue
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope='session',autouse=True)
def close_engine():
    yield
    engine.dispose()
    test_directory.cleanup()

@pytest.fixture
def db():
    with Session() as session:yield session

@pytest.fixture
def client():
    with TestClient(app) as c:
        with Session() as db:
            user=db.query(User).filter_by(email='admin@test.local').one()
            token=issue(user)
        c.cookies.set('session',token);c.cookies.set('csrf','test-csrf')
        c.headers.update({'origin':'http://localhost:3000','x-csrf-token':'test-csrf'})
        yield c
