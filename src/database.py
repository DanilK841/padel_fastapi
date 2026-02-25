import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv
from asyncpg import Connection
from uuid import uuid4
from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, String,
    func, DateTime,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship

load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB_URL")

class Base(DeclarativeBase): pass

postgres_file_name = f"{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_DB}"
# DATABASE_URL = os.getenv(
#     "DATABASE_URL",
#     "postgresql+asyncpg:///{sqlite_file_name}"
#     )

DATABASE_URL = f"postgresql+asyncpg://{postgres_file_name}"

class FixedConnection(Connection):
    def _get_unique_id(self, prefix: str) -> str:
        return f'__asyncpg_{prefix}_{uuid4()}__'


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "connection_class": FixedConnection,
    }
)

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

#ORM

class TournamentORM(Base):
    __tablename__ = "tournaments"

    id            = Column(String, primary_key=True)
    mode          = Column(String, nullable=False, default="americano")  # americano | mexicano
    name          = Column(String, nullable=False)
    courts        = Column(Integer, nullable=False)
    status        = Column(String, nullable=False, default="setup")
    current_round = Column(Integer, nullable=False, default=0)
    total_rounds  = Column(Integer, nullable=False, default=0)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    players = relationship(
        "PlayerORM",
        back_populates="tournament",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    matches = relationship(
        "MatchORM",
        back_populates="tournament",
        cascade="all, delete-orphan",
        order_by="MatchORM.round, MatchORM.court",
        lazy="selectin",
    )


class PlayerORM(Base):
    __tablename__ = "players"

    id            = Column(String, primary_key=True)
    tournament_id = Column(String, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    name          = Column(String, nullable=False)
    sex           = Column(String, nullable=False, default='M')  # M | F
    points        = Column(Integer, nullable=False, default=0)
    games_played  = Column(Integer, nullable=False, default=0)
    games_won     = Column(Integer, nullable=False, default=0)
    games_lost    = Column(Integer, nullable=False, default=0)

    tournament = relationship("TournamentORM", back_populates="players")


class MatchORM(Base):
    __tablename__ = "matches"

    id            = Column(String, primary_key=True)
    tournament_id = Column(String, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    round         = Column(Integer, nullable=False)
    court         = Column(Integer, nullable=False)
    team1         = Column(JSONB, nullable=False)   # list[str] -- player ids
    team2         = Column(JSONB, nullable=False)
    score1        = Column(Integer, nullable=True)
    score2        = Column(Integer, nullable=True)
    completed     = Column(Boolean, nullable=False, default=False)

    tournament = relationship("TournamentORM", back_populates="matches")



