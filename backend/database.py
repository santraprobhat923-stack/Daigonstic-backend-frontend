from sqlalchemy import create_engine,event
from sqlalchemy.orm import declarative_base,sessionmaker
from .config import DATABASE_URL
engine=create_engine(DATABASE_URL,connect_args={"check_same_thread":False,"timeout":30} if DATABASE_URL.startswith("sqlite") else {})
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine,"connect")
    def _sqlite_concurrency(dbapi_connection,connection_record):
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        dbapi_connection.execute("PRAGMA busy_timeout=30000")
SessionLocal=sessionmaker(bind=engine,autocommit=False,autoflush=False)
Base=declarative_base()
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
