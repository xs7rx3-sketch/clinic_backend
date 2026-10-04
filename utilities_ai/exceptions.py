class UtilitiesAIError(Exception):
    """Base exception for all utilities-ai errors."""


class ConfigurationError(UtilitiesAIError):
    """Raised when configuration or environment variables are invalid."""


# TODO: This must be modified so that a new class is created for each sub-package, each has to sub-class `ConnectionError`.
class ConnectionError(UtilitiesAIError):
    """Raised when a connection cannot be established."""
