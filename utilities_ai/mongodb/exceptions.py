class MongoError(Exception):
    """Base exception for all MongoDB sub-package errors."""


class MongoConfigurationError(MongoError):
    """Configuration error in MongoDB."""


class MongoPoolError(MongoError):
    """Pool-related errors in MongoDB."""


class MongoPoolConfigurationError(MongoError):
    """Pool-related configuration errors in MongoDB."""
