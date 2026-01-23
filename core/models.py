from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Article:
    title: str
    url: str
    source: str  # Domain or site name
    published_at: Optional[datetime]
    summary: str  # Short description or snippet
    content_hash: str  # For deduplication (md5 of url or content)
    content: Optional[str] = None # Full text content
    score: float = 0.0  # Gemini relevance score (0-10)
    relevance_reason: Optional[str] = None # Reason for the score
