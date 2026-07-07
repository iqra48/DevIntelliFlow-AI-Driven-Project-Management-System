class GroqGovernorLimitExceeded(RuntimeError):
    pass


class StrictProviderFallbackBlocked(RuntimeError):
    pass


class ProviderFallbackUnavailable(RuntimeError):
    pass
