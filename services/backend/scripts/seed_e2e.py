import sys
from datetime import datetime, timezone
from os import environ
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from urllib.parse import urlsplit
from uuid import uuid4
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models.catalogue import Issuer, IssuerDomain, SourceEvidence, ModerationDecision, Opportunity
from app.services.catalogue import OpportunityFields, publish_approved

url = environ['DATABASE_URL']
if urlsplit(url).path != '/jejakpeluang_e2e':
    raise RuntimeError('E2E seed requires the isolated test database')
now = datetime.now(timezone.utc)
with Session(create_engine(url)) as session:
    if session.scalar(select(Opportunity).where(Opportunity.slug == 'uji-peluang')):
        raise SystemExit(0)
    issuer = Issuer(name='Example University')
    session.add(issuer)
    session.flush()
    session.add(IssuerDomain(issuer_id=issuer.id, domain='example.org', verified_at=now))
    source = SourceEvidence(issuer_id=issuer.id, url='https://example.org/notice', retrieved_at=now)
    session.add(source)
    session.flush()
    decision = ModerationDecision(source_evidence_id=source.id, actor_id=uuid4(),
        status='approved', decided_at=now)
    session.add(decision)
    session.flush()
    publish_approved(session, issuer_id=issuer.id, evidence_id=source.id,
        source_url=source.url, decision_id=decision.id,
        fields=OpportunityFields(slug='uji-peluang', title='Uji Peluang',
            category='scholarship', description='Data uji sintetik', eligibility='Pelajar',
            region=None, deadline=None, checked_at=now))
    session.commit()
