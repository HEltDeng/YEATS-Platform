from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

class Base(DeclarativeBase): pass

if settings.database_url.startswith('sqlite:'): Path('runtime').mkdir(exist_ok=True)
engine = create_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True, connect_args={'check_same_thread':False} if settings.database_url.startswith('sqlite:') else {})
if settings.database_url.startswith('sqlite:'):
    @event.listens_for(engine, 'connect')
    def sqlite_fk(conn, record): conn.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(engine, expire_on_commit=False)
def database():
    with SessionLocal() as db:
        try: yield db
        except Exception:
            db.rollback()
            raise
