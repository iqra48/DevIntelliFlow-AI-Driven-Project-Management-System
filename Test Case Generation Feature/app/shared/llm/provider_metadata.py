import contextvars


request_provider_metadata_ctx = contextvars.ContextVar(
    "request_provider_metadata",
    default=None,
)
