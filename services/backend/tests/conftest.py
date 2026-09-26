from datetime import datetime, timezone
from secrets import token_urlsafe
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base, get_session
from app.main import app
from app.models.auth import AccessToken, User
from app.models.catalogue import Issuer, IssuerDomain, SourceEvidence, ModerationDecision
from app.services.catalogue import OpportunityFields, publish_approved

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from app import security
    security.rate_limiter.reset()
    security._configured_limiter = None
    yield
    security.rate_limiter.reset()
    security._configured_limiter = None


@pytest.fixture
def session():
    engine = create_engine('sqlite+pysqlite:///:memory:',
        connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.fixture
def client(session):
    def override():
        yield session
    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


password_hasher = PasswordHash((Argon2Hasher(),))


@pytest.fixture
def make_user(session):
    def build(email, password='correct-horse', *, role='moderator'):
        user = User(email=email, hashed_password=password_hasher.hash(password),
            is_active=True, is_verified=True, role=role)
        session.add(user)
        session.commit()
        return user
    return build


@pytest.fixture
def auth_cookie(session):
    def build(user):
        token = AccessToken(token=token_urlsafe(32), user_id=user.id)
        session.add(token)
        session.commit()
        return token.token
    return build


@pytest.fixture
def verified_issuer(session):
    issuer = Issuer(name='Example University')
    session.add(issuer)
    session.flush()
    session.add(IssuerDomain(issuer_id=issuer.id, domain='example.org', verified_at=NOW))
    session.flush()
    return issuer


@pytest.fixture
def official_source(session, verified_issuer):
    source = SourceEvidence(issuer_id=verified_issuer.id,
        url='https://example.org/notice', retrieved_at=NOW)
    session.add(source)
    session.flush()
    return source


@pytest.fixture
def approved_decision(session, official_source):
    decision = ModerationDecision(source_evidence_id=official_source.id,
        actor_id=uuid4(), status='approved', decided_at=NOW)
    session.add(decision)
    session.flush()
    return decision


@pytest.fixture
def valid_fields():
    return OpportunityFields(slug='uji-peluang', title='Uji Peluang',
        category='scholarship', description='Data uji sintetik',
        eligibility='Pelajar', region=None, deadline=None, checked_at=NOW)


@pytest.fixture
def make_entry(session, verified_issuer, official_source, valid_fields):
    def build(slug, *, status='published', deadline=None):
        decision = ModerationDecision(source_evidence_id=official_source.id,
            actor_id=uuid4(), status='approved', decided_at=NOW)
        session.add(decision)
        session.flush()
        fields = valid_fields.model_copy(update={'slug': slug, 'deadline': deadline})
        item = publish_approved(session, issuer_id=verified_issuer.id,
            evidence_id=official_source.id, source_url=official_source.url,
            decision_id=decision.id, fields=fields)
        item.status = status
        session.flush()
        return item
    return build
