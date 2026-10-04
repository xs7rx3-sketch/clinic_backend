class ChainError(Exception):
    """Base exception for all chains sub-package errors."""


class ChainConfigurationError(ChainError):
    """Configuration error in the chains sub-package."""


class ChainTypeError(ChainError, ValueError):
    """Invalid value type in the chains sub-package."""


class ChainServiceError(ChainError):
    """Base exception for all chain services errors."""


class InvalidFileExtension(ChainServiceError, NotImplementedError):
    """Invalid file extension provided in the files to text service."""
