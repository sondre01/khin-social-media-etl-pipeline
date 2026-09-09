import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    text,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.orm import declarative_base, sessionmaker

from sqlalchemy.engine import URL

# Load environment variables from .env file in the project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DB_USER = os.getenv("DB_USER", "etl_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secretpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "social_data")

# Using URL.create to safely escape special characters in password
DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class SocialPost(Base):
    """
    Hybrid model storing transformed relational attributes alongside
    the complete raw API payload in JSONB.
    """
    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, index=True)
    post_id = Column(String(100), nullable=False, unique=True, index=True)
    title = Column(Text, nullable=True)
    author = Column(String(100), nullable=True)
    content = Column(Text, nullable=True)
    score = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    url = Column(Text, nullable=True)
    post_created_at = Column(DateTime(timezone=True), nullable=True)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())
    raw_data = Column(JSONB, nullable=False)

    def __repr__(self):
        return f"<SocialPost(platform='{self.platform}', post_id='{self.post_id}', title='{self.title[:30] if self.title else ''}')>"


def create_tables():
    """Create all tables defined in Base metadata if they do not exist."""
    Base.metadata.create_all(bind=engine)
    print("Tables verified / created successfully.")


def test_connection():
    """Verify connectivity to the PostgreSQL instance and test SELECT 1."""
    print(f"Testing database connection to {DB_HOST}:{DB_PORT}/{DB_NAME} as '{DB_USER}'...")
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1;")).scalar()
            print(f"Connection successful! Test query returned: {result}")
        create_tables()
        return True
    except Exception as exc:
        print(f"Database connection failed: {exc}")
        return False


def load_posts_to_db(df) -> int:
    """
    Load stage: Upsert cleaned posts into the PostgreSQL database.
    If a post already exists (same post_id), update its score and comments count.
    """
    if df is None or df.empty:
        print("[LOAD] No records to load.")
        return 0

    print(f"[LOAD] Loading {len(df)} records into PostgreSQL table 'social_posts'...")
    create_tables()

    records = df.to_dict(orient="records")
    loaded_count = 0

    with SessionLocal() as session:
        for record in records:
            stmt = pg_insert(SocialPost).values(**record)
            # Handle duplicates: update score, comments, title, and raw payload
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["post_id"],
                set_={
                    "score": stmt.excluded.score,
                    "num_comments": stmt.excluded.num_comments,
                    "title": stmt.excluded.title,
                    "raw_data": stmt.excluded.raw_data,
                },
            )
            session.execute(upsert_stmt)
            loaded_count += 1
        session.commit()

    print(f"[LOAD] Successfully upserted {loaded_count} posts into database!")
    return loaded_count


def query_stored_posts(limit: int = 5):
    """Utility function to read and display saved posts from the database."""
    with SessionLocal() as session:
        posts = session.query(SocialPost).order_by(SocialPost.id.desc()).limit(limit).all()
        print(f"\n--- Stored Posts in PostgreSQL (Showing {len(posts)}) ---")
        for p in posts:
            print(f"ID #{p.id} | [{p.score} likes, {p.num_comments} comments] {p.title} (by {p.author})")


if __name__ == "__main__":
    if test_connection():
        query_stored_posts()

