import copy
import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from app.services.test_case_generation.models import (
    RequirementForTestCase,
    TestCaseGenerationResult,
)
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
)


def is_cache_enabled() -> bool:
    """
    Return False only when TEST_CASE_CACHE_ENABLED is false/0/no.
    """
    value = os.getenv("TEST_CASE_CACHE_ENABLED", "true").strip().casefold()
    return value not in {"false", "0", "no"}


def _cache_ttl_seconds() -> int:
    return int(os.getenv("TEST_CASE_CACHE_TTL_SECONDS", "3600"))


def _cache_max_entries() -> int:
    return int(os.getenv("TEST_CASE_CACHE_MAX_ENTRIES", "128"))


def _stable_json(value: Any) -> str:
    """
    json.dumps with stable separators and key ordering.
    """
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_cache_key(
    requirements: list[RequirementForTestCase],
    project_context: str | None,
    mode: str,
) -> str:
    """
    Build stable SHA256 cache key.
    """
    payload = {
        "requirements": [
            {
                "id": requirement.id,
                "requirement": requirement.requirement,
                "classification_type": requirement.classification_type,
            }
            for requirement in requirements
        ],
        "project_context": project_context or "",
        "mode": mode,
        "planner_prompt_version": TEST_CASE_PROMPT_VERSION,
        "generator_prompt_version": TEST_CASE_GENERATOR_PROMPT_VERSION,
        "reviewer_prompt_version": TEST_CASE_REVIEWER_PROMPT_VERSION,
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


@dataclass
class CacheEntry:
    key: str
    created_at: float
    result: dict


_TEST_CASE_CACHE: dict[str, CacheEntry] = {}


def get_cached_result(key: str) -> TestCaseGenerationResult | None:
    """
    Return deep-copied TestCaseGenerationResult if present and not expired.
    """
    if not is_cache_enabled():
        return None

    entry = _TEST_CASE_CACHE.get(key)
    if entry is None:
        return None

    if time.time() - entry.created_at > _cache_ttl_seconds():
        _TEST_CASE_CACHE.pop(key, None)
        return None

    try:
        return TestCaseGenerationResult.from_dict(copy.deepcopy(entry.result))
    except Exception:
        _TEST_CASE_CACHE.pop(key, None)
        return None


def _evict_old_entries() -> None:
    max_entries = _cache_max_entries()
    while len(_TEST_CASE_CACHE) > max_entries:
        oldest_key = min(
            _TEST_CASE_CACHE,
            key=lambda cache_key: _TEST_CASE_CACHE[cache_key].created_at,
        )
        _TEST_CASE_CACHE.pop(oldest_key, None)


def store_cached_result(key: str, result: TestCaseGenerationResult) -> None:
    """
    Store a deep copied result dict.
    """
    if not is_cache_enabled():
        return

    if result.status in {"PROVIDER_FAILED", "RATE_LIMITED"}:
        return

    _TEST_CASE_CACHE[key] = CacheEntry(
        key=key,
        created_at=time.time(),
        result=copy.deepcopy(result.to_dict()),
    )
    _evict_old_entries()


def clear_test_case_cache() -> None:
    """
    Used by tests.
    """
    _TEST_CASE_CACHE.clear()


def cache_stats() -> dict:
    """
    Return cache status and configuration.
    """
    return {
        "enabled": is_cache_enabled(),
        "size": len(_TEST_CASE_CACHE),
        "ttl_seconds": _cache_ttl_seconds(),
        "max_entries": _cache_max_entries(),
    }
