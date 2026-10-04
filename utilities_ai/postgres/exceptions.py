class PostgresError(Exception):
    """Base exception for all Postgres sub-package errors."""


class PostgresConfigurationError(PostgresError):
    """Configuration error in the Postgres sub-package."""


class PostgresValueError(PostgresError, ValueError):
    """Invalid value error in the Postgres sub-package."""


class PostgresTypeError(PostgresError, TypeError):
    """Invalid value type in the Postgres sub-package."""
