import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.exceptions import RequestValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.api.routes import router
from app.db import Base, get_db
from app.models import User
from app.auth import verify_password
from app.main import validation_error

@pytest.fixture
def signup_client():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(RequestValidationError, validation_error)
    def database():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, sessions
    engine.dispose()

def test_signup_login_and_protected_access(signup_client):
    client, sessions = signup_client
    response = client.post('/api/auth/register', json={'email': ' New@Example.com ', 'password': 'secret-password'})
    assert response.status_code == 201
    with sessions() as db:
        user = db.scalar(select(User))
        assert user.email == 'new@example.com'
        assert user.password_hash != 'secret-password'
        assert verify_password('secret-password', user.password_hash)
    login = client.post('/api/auth/login', data={'username': ' NEW@example.com ', 'password': 'secret-password'})
    assert login.status_code == 200
    assert client.get('/api/scans', headers={'Authorization': 'Bearer ' + login.json()['access_token']}).status_code == 200
    assert client.post('/api/auth/login', data={'username': 'new@example.com', 'password': 'wrong-password'}).status_code == 401
    duplicate = client.post('/api/auth/register', json={'email': 'NEW@example.com', 'password': 'another-password'})
    assert duplicate.status_code == 409
    assert duplicate.json() == {'detail': 'Unable to create account with these details'}
    with sessions() as db:
        assert len(list(db.scalars(select(User)))) == 1

@pytest.mark.parametrize('email,password', [('bad', 'secret-password'), ('new@example.com', 'short'), ('new@example.com', 'x'*129), ('new@example.com', ' '*8)])
def test_invalid_signup_does_not_echo_input_or_create_users(signup_client, email, password):
    client, sessions = signup_client
    response = client.post('/api/auth/register', json={'email': email, 'password': password})
    assert response.status_code == 422
    assert 'input' not in response.text
    assert all(error['msg'] == 'Invalid request value' and 'input' not in error for error in response.json()['detail'])
    with sessions() as db:
        assert db.scalar(select(User)) is None

def test_duplicate_commit_race_is_safe_and_rolls_back(signup_client, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    client, _ = signup_client
    rollbacks = []
    original = Session.rollback
    def fail_commit(_self):
        raise IntegrityError('private SQL', {}, Exception('private database detail'))
    def rollback(self):
        rollbacks.append(True)
        return original(self)
    monkeypatch.setattr(Session, 'commit', fail_commit)
    monkeypatch.setattr(Session, 'rollback', rollback)
    response = client.post('/api/auth/register', json={'email': 'race@example.com', 'password': 'secret-password'})
    assert response.status_code == 409
    assert response.json() == {'detail': 'Unable to create account with these details'}
    assert rollbacks
