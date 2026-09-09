import requests
from typing import List, Dict, Any


def fetch_posts(tag: str = "python", per_page: int = 10) -> List[Dict[str, Any]]:
    """
    Extract stage: Fetch recent articles from Dev.to API.
    
    :param tag: Optional topic tag (e.g. 'python', 'beginners', 'ai')
    :param per_page: Number of posts to retrieve (max 30)
    :return: List of raw article dictionaries
    """
    url = "https://dev.to/api/articles"
    params = {
        "tag": tag,
        "per_page": per_page,
    }
    headers = {
        "User-Agent": "social-media-etl-pipeline/1.0"
    }

    print(f"[EXTRACT] Calling Dev.to API (tag='{tag}', per_page={per_page})...")
    
    response = requests.get(url, params=params, headers=headers, timeout=10)
    
    # Raise an error if the request failed (e.g. 404, 500)
    response.raise_for_status()

    raw_posts = response.json()
    print(f"[EXTRACT] Successfully retrieved {len(raw_posts)} raw posts.")
    return raw_posts


if __name__ == "__main__":
    # Test our extraction logic directly
    posts = fetch_posts(tag="python", per_page=5)
    print("\n--- Quick Preview of Extracted Posts ---")
    for index, post in enumerate(posts, start=1):
        author = post.get("user", {}).get("name", "Unknown")
        print(f"{index}. [{post.get('public_reactions_count')} likes] {post.get('title')} (by {author})")
