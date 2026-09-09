from datetime import datetime
from typing import List, Dict, Any
import pandas as pd


def parse_iso_datetime(date_str: str) -> datetime | None:
    """Helper to convert ISO 8601 string into a Python datetime object."""
    if not date_str:
        return None
    try:
        # Dev.to format: '2026-09-09T13:00:00Z'
        # Replace 'Z' with '+00:00' so Python's fromisoformat parses UTC correctly
        clean_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None


def clean_posts(raw_posts: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Transform stage: Clean, validate, and flatten raw Dev.to JSON posts.
    
    :param raw_posts: List of raw dictionaries returned by extract/client.py
    :return: Cleaned Pandas DataFrame ready for database insertion
    """
    print(f"[TRANSFORM] Cleaning and transforming {len(raw_posts)} raw posts...")
    cleaned_records = []

    for post in raw_posts:
        user_info = post.get("user") or {}
        
        record = {
            "platform": "dev.to",
            "post_id": str(post.get("id")),
            "title": post.get("title", "").strip() if post.get("title") else None,
            "author": user_info.get("name", "Unknown"),
            "content": post.get("description", ""),
            "score": int(post.get("public_reactions_count", 0)),
            "num_comments": int(post.get("comments_count", 0)),
            "url": post.get("url"),
            "post_created_at": parse_iso_datetime(post.get("published_at")),
            # Crucial: Keep the COMPLETE untouched JSON dictionary for our PostgreSQL JSONB column
            "raw_data": post,
        }
        cleaned_records.append(record)

    df = pd.DataFrame(cleaned_records)
    print(f"[TRANSFORM] Successfully prepared DataFrame with shape: {df.shape} (rows, columns).")
    return df


if __name__ == "__main__":
    # Test extract + transform together!
    import sys
    from pathlib import Path

    # Add project root to path so we can import extract
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from extract.client import fetch_posts

    sample_raw = fetch_posts(tag="python", per_page=3)
    sample_df = clean_posts(sample_raw)

    print("\n--- Cleaned Data Preview (Pandas Table) ---")
    # Display key columns in terminal
    display_cols = ["post_id", "author", "score", "num_comments", "title"]
    print(sample_df[display_cols].to_string(index=False))
