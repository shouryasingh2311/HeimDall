"""
Collector Adapters Package.
Owned by Member 3 (feat/fixtures-validation).
Provides input adapters transforming raw source data into canonical RawEvents.
"""

from .jsonl_adapter import JSONLAdapter
from .organizer_adapter import OrganizerAdapter

__all__ = ["JSONLAdapter", "OrganizerAdapter"]
