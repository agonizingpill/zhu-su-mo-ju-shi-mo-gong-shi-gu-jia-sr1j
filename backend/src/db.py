import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
engine = create_engine(os.environ['DATABASE_URL'], pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
def migrate():
    # Non-destructive column additions for databases created before rate versioning.
    for stmt in ('ALTER TABLE estimates ADD COLUMN rate_version VARCHAR(60)','ALTER TABLE estimates ADD COLUMN rate_invalid_reason VARCHAR(300)'):
        try:
            with engine.begin() as c: c.execute(text(stmt))
        except Exception: pass  # column already exists
def db_session():
    with Session() as s:
        yield s
