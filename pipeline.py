"""
pipeline.py - Orchestrator for Social Media ETL Pipeline

Lifecycle:
  1. EXTRACT   -> fetch raw social media posts via API
  2. TRANSFORM -> clean, validate, and flatten data with Pandas
  3. LOAD      -> persist structured records + raw JSONB into PostgreSQL
"""

from extract.client import fetch_posts
from transform.cleaner import clean_posts
from load.db import load_posts_to_db, query_stored_posts


def run_pipeline(tag: str = "python", limit: int = 10):
    print("=" * 60)
    print(f"[START] SOCIAL MEDIA ETL PIPELINE (Tag: '{tag}', Limit: {limit})")
    print("=" * 60)

    # 1. EXTRACT
    raw_posts = fetch_posts(tag=tag, per_page=limit)
    if not raw_posts:
        print("[PIPELINE] No posts extracted. Exiting.")
        return

    # 2. TRANSFORM
    cleaned_df = clean_posts(raw_posts)
    if cleaned_df.empty:
        print("[PIPELINE] No valid records after cleaning. Exiting.")
        return

    # 3. LOAD
    total_loaded = load_posts_to_db(cleaned_df)

    print("\n" + "=" * 60)
    print(f"[SUCCESS] PIPELINE COMPLETED! {total_loaded} records processed.")
    print("=" * 60)

    # 4. INSPECT STORED DATA
    query_stored_posts(limit=5)


if __name__ == "__main__":
    run_pipeline(tag="python", limit=5)
