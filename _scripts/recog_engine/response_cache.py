"""
ReCog - Response Caching v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Caches LLM extraction results to avoid paying twice for the same content.
Uses content hashing to identify duplicate documents.

Default: Filesystem cache (no external dependencies)
Optional: Redis backend for distributed deployments
"""

import hashlib
import json
import logging
import os
import pickle
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default cache TTL (24 hours)
DEFAULT_TTL_SECONDS = 24 * 60 * 60

# Maximum cache size in MB (for filesystem cache)
DEFAULT_MAX_SIZE_MB = 500

# Cache key prefixes
PREFIX_EXTRACTION = "extract"
PREFIX_TIER0 = "tier0"
PREFIX_ENTITY = "entity"


@dataclass
class CacheEntry:
    """A cached response with metadata."""
    key: str
    value: Any
    created_at: float  # Unix timestamp
    expires_at: float  # Unix timestamp
    content_hash: str
    feature: str  # extraction, tier0, entity
    hit_count: int = 0
    last_accessed: float = 0


@dataclass
class CacheStats:
    """Cache statistics."""
    total_entries: int
    total_size_bytes: int
    hits: int
    misses: int
    hit_rate: float
    oldest_entry: Optional[datetime]
    newest_entry: Optional[datetime]


class ResponseCache:
    """
    Caches LLM responses by content hash.

    Usage:
        cache = ResponseCache(cache_dir)

        # Check cache before calling LLM
        cached = cache.get_extraction(content_hash)
        if cached:
            return cached

        # Call LLM and cache result
        result = call_llm(content)
        cache.set_extraction(content_hash, result)

    Content hashing ensures the same document always gets the same
    cached result, regardless of filename or upload time.
    """

    def __init__(
        self,
        cache_dir: Union[str, Path],
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_size_mb: int = DEFAULT_MAX_SIZE_MB,
    ):
        """
        Initialize cache.

        Args:
            cache_dir: Directory for cache files
            ttl_seconds: Time-to-live in seconds (default: 24 hours)
            max_size_mb: Maximum cache size in MB
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.max_size_bytes = max_size_mb * 1024 * 1024

        # In-memory stats
        self._hits = 0
        self._misses = 0

        logger.info(f"Response cache initialized: {self.cache_dir} (TTL: {ttl_seconds}s)")

    # =========================================================================
    # CONTENT HASHING
    # =========================================================================

    @staticmethod
    def hash_content(content: str) -> str:
        """
        Generate SHA-256 hash of content.

        This ensures the same document always produces the same hash,
        regardless of filename, upload time, or other metadata.
        """
        # Normalize: strip whitespace, lowercase for consistency
        normalized = content.strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_with_context(content: str, context: Dict[str, Any] = None) -> str:
        """
        Generate hash including extraction context.

        Use this when the same content might need different analysis
        based on case context, entity registry state, etc.
        """
        parts = [content.strip()]
        if context:
            # Sort keys for consistent hashing
            context_str = json.dumps(context, sort_keys=True)
            parts.append(context_str)
        combined = "||".join(parts)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    # =========================================================================
    # CACHE OPERATIONS
    # =========================================================================

    def _get_cache_path(self, key: str) -> Path:
        """Get filesystem path for a cache key."""
        # Use first 2 chars of hash for subdirectory (reduces files per dir)
        subdir = key[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(exist_ok=True)
        return cache_subdir / f"{key}.cache"

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if cache entry has expired."""
        return time.time() > entry.expires_at

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key (typically a content hash)

        Returns:
            Cached value or None if not found/expired
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            self._misses += 1
            return None

        try:
            with open(cache_path, "rb") as f:
                entry: CacheEntry = pickle.load(f)

            # Check expiration
            if self._is_expired(entry):
                logger.debug(f"Cache expired: {key[:16]}...")
                cache_path.unlink(missing_ok=True)
                self._misses += 1
                return None

            # Update access stats
            entry.hit_count += 1
            entry.last_accessed = time.time()

            # Save updated stats (async would be better but not critical)
            try:
                with open(cache_path, "wb") as f:
                    pickle.dump(entry, f)
            except Exception:
                pass  # Stats update failure is not critical

            self._hits += 1
            logger.debug(f"Cache hit: {key[:16]}... (hits: {entry.hit_count})")
            return entry.value

        except Exception as e:
            logger.warning(f"Cache read error for {key[:16]}...: {e}")
            self._misses += 1
            return None

    def set(
        self,
        key: str,
        value: Any,
        feature: str = "unknown",
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Store value in cache.

        Args:
            key: Cache key (typically a content hash)
            value: Value to cache
            feature: Feature name for tracking (extraction, tier0, etc.)
            ttl_seconds: Override TTL for this entry

        Returns:
            True if cached successfully
        """
        ttl = ttl_seconds or self.ttl_seconds
        now = time.time()

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            expires_at=now + ttl,
            content_hash=key,
            feature=feature,
            hit_count=0,
            last_accessed=now,
        )

        cache_path = self._get_cache_path(key)

        try:
            with open(cache_path, "wb") as f:
                pickle.dump(entry, f)
            logger.debug(f"Cached: {key[:16]}... (feature: {feature})")
            return True
        except Exception as e:
            logger.warning(f"Cache write error for {key[:16]}...: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        cache_path = self._get_cache_path(key)
        try:
            cache_path.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def clear(self, feature: Optional[str] = None) -> int:
        """
        Clear cache entries.

        Args:
            feature: If specified, only clear entries for this feature

        Returns:
            Number of entries cleared
        """
        cleared = 0

        for subdir in self.cache_dir.iterdir():
            if not subdir.is_dir():
                continue

            for cache_file in subdir.glob("*.cache"):
                try:
                    if feature:
                        # Load and check feature
                        with open(cache_file, "rb") as f:
                            entry: CacheEntry = pickle.load(f)
                        if entry.feature != feature:
                            continue

                    cache_file.unlink()
                    cleared += 1
                except Exception:
                    pass

        logger.info(f"Cache cleared: {cleared} entries" + (f" (feature: {feature})" if feature else ""))
        return cleared

    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        removed = 0
        now = time.time()

        for subdir in self.cache_dir.iterdir():
            if not subdir.is_dir():
                continue

            for cache_file in subdir.glob("*.cache"):
                try:
                    with open(cache_file, "rb") as f:
                        entry: CacheEntry = pickle.load(f)

                    if now > entry.expires_at:
                        cache_file.unlink()
                        removed += 1
                except Exception:
                    # Remove corrupted entries
                    try:
                        cache_file.unlink()
                        removed += 1
                    except Exception:
                        pass

        if removed > 0:
            logger.info(f"Expired cache cleanup: {removed} entries removed")
        return removed

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def get_extraction(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached extraction result."""
        key = f"{PREFIX_EXTRACTION}:{content_hash}"
        return self.get(key)

    def set_extraction(
        self,
        content_hash: str,
        result: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Cache extraction result."""
        key = f"{PREFIX_EXTRACTION}:{content_hash}"
        return self.set(key, result, feature="extraction", ttl_seconds=ttl_seconds)

    def get_tier0(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached Tier 0 result."""
        key = f"{PREFIX_TIER0}:{content_hash}"
        return self.get(key)

    def set_tier0(
        self,
        content_hash: str,
        result: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Cache Tier 0 result."""
        key = f"{PREFIX_TIER0}:{content_hash}"
        return self.set(key, result, feature="tier0", ttl_seconds=ttl_seconds)

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        total_entries = 0
        total_size = 0
        oldest = None
        newest = None

        for subdir in self.cache_dir.iterdir():
            if not subdir.is_dir():
                continue

            for cache_file in subdir.glob("*.cache"):
                try:
                    stat = cache_file.stat()
                    total_entries += 1
                    total_size += stat.st_size

                    mtime = datetime.fromtimestamp(stat.st_mtime)
                    if oldest is None or mtime < oldest:
                        oldest = mtime
                    if newest is None or mtime > newest:
                        newest = mtime
                except Exception:
                    pass

        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return CacheStats(
            total_entries=total_entries,
            total_size_bytes=total_size,
            hits=self._hits,
            misses=self._misses,
            hit_rate=hit_rate,
            oldest_entry=oldest,
            newest_entry=newest,
        )


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_cache_instance: Optional[ResponseCache] = None


def get_response_cache(cache_dir: Optional[Path] = None) -> ResponseCache:
    """
    Get the global response cache instance.

    Args:
        cache_dir: Cache directory (only needed on first call)

    Returns:
        ResponseCache instance
    """
    global _cache_instance

    if _cache_instance is None:
        if cache_dir is None:
            # Default to _data/cache relative to _scripts directory
            scripts_dir = Path(__file__).parent.parent
            cache_dir = scripts_dir / "_data" / "cache"
        _cache_instance = ResponseCache(cache_dir)

    return _cache_instance


def init_response_cache(cache_dir: Path, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> ResponseCache:
    """Initialize the global response cache with custom settings."""
    global _cache_instance
    _cache_instance = ResponseCache(cache_dir, ttl_seconds=ttl_seconds)
    return _cache_instance


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "ResponseCache",
    "CacheEntry",
    "CacheStats",
    "get_response_cache",
    "init_response_cache",
    "DEFAULT_TTL_SECONDS",
]
