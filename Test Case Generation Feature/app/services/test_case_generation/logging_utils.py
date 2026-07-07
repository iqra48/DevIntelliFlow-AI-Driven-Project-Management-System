def log_test_case_request_start(
    logger,
    mode: str,
    requirement_count: int,
    estimated_calls: int,
    estimated_tokens: int,
) -> None:
    logger.info(
        "event=TEST_CASE_REQUEST_START mode=%s requirement_count=%s "
        "estimated_calls=%s estimated_tokens=%s",
        mode,
        requirement_count,
        estimated_calls,
        estimated_tokens,
    )


def log_test_case_cache_event(
    logger,
    event: str,
    cache_key: str,
    mode: str,
    requirement_count: int,
) -> None:
    logger.info(
        "event=%s cache_key_prefix=%s mode=%s requirement_count=%s",
        event,
        cache_key[:12],
        mode,
        requirement_count,
    )


def log_test_case_chunk(
    logger,
    mode: str,
    chunk_index: int,
    chunk_size: int,
    safe_count: int,
    blocked_count: int,
) -> None:
    logger.info(
        "event=TEST_CASE_CHUNK mode=%s chunk_index=%s chunk_size=%s "
        "safe_count=%s blocked_count=%s",
        mode,
        chunk_index,
        chunk_size,
        safe_count,
        blocked_count,
    )


def log_test_case_requirement_result(
    logger,
    requirement_id: str,
    requirement_type: str,
    status: str,
    test_case_count: int,
    risk_level: str | None = None,
    mode: str | None = None,
) -> None:
    logger.info(
        "event=TEST_CASE_REQUIREMENT_RESULT requirement_id=%s "
        "requirement_type=%s status=%s test_case_count=%s risk_level=%s mode=%s",
        requirement_id,
        requirement_type,
        status,
        test_case_count,
        risk_level or "",
        mode or "",
    )


def log_test_case_request_complete(
    logger,
    mode: str,
    final_status: str,
    requirement_count: int,
    calls_used: int,
    estimated_tokens: int,
    cache_hit: bool,
    elapsed_ms: int | None = None,
) -> None:
    logger.info(
        "event=TEST_CASE_REQUEST_COMPLETE mode=%s final_status=%s "
        "requirement_count=%s calls_used=%s estimated_tokens=%s cache_hit=%s "
        "elapsed_ms=%s",
        mode,
        final_status,
        requirement_count,
        calls_used,
        estimated_tokens,
        cache_hit,
        "" if elapsed_ms is None else elapsed_ms,
    )
