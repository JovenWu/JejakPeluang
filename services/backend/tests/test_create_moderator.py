import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models.auth import User


@pytest.fixture
def script(monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'create_moderator.py'
    spec = importlib.util.spec_from_file_location('create_moderator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    test_engine = create_engine('sqlite+pysqlite:///:memory:',
        connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(test_engine)
    monkeypatch.setattr(module, 'engine', lambda: test_engine)
    yield module, test_engine
    test_engine.dispose()


def run(module, argv, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', argv)
    code = module.main()
    return code, capsys.readouterr()


def test_create_moderator_generates_password(script, monkeypatch, capsys):
    module, test_engine = script
    code, out = run(module, ['create_moderator.py', 'new@example.org'],
        monkeypatch, capsys)
    assert code == 0
    assert 'password:' in out.out
    with Session(test_engine) as session:
        user = session.execute(select(User).where(
            User.email == 'new@example.org')).scalar_one()
        assert user.role == 'moderator'
        assert user.is_active
        assert user.hashed_password


def test_create_moderator_explicit_password(script, monkeypatch, capsys):
    module, test_engine = script
    code, out = run(module,
        ['create_moderator.py', 'new@example.org', '--password', 's3cret'],
        monkeypatch, capsys)
    assert code == 0
    assert 'password:' not in out.out
    with Session(test_engine) as session:
        user = session.execute(select(User).where(
            User.email == 'new@example.org')).scalar_one()
        assert module.password_helper.verify_and_update(
            's3cret', user.hashed_password)[0]


def test_create_moderator_prints_normalized_email(script, monkeypatch, capsys):
    module, test_engine = script
    code, out = run(module,
        ['create_moderator.py', 'MixedCase@Example.ORG', '--password', 's3cret'],
        monkeypatch, capsys)
    assert code == 0
    assert 'created moderator mixedcase@example.org' in out.out
    with Session(test_engine) as session:
        user = session.execute(select(User).where(
            User.email == 'mixedcase@example.org')).scalar_one()
        assert user.role == 'moderator'


def test_create_moderator_refuses_duplicate(script, monkeypatch, capsys):
    module, _ = script
    argv = ['create_moderator.py', 'dup@example.org', '--password', 's3cret']
    code, _ = run(module, argv, monkeypatch, capsys)
    assert code == 0
    code, out = run(module, argv, monkeypatch, capsys)
    assert code == 1
    assert 'already exists' in out.err
