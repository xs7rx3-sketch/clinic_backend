DEFAULT_ENABLE_LOGGER = True
DEFAULT_LOG_LEVEL = "INFO"

DEFAULT_LOG_FILE_PATH = "app.log"
DEFAULT_MAX_FILE_SIZE = 10 * 2**20  # 10 MB
DEFAULT_RETAINED_FILE_COUNT = 5

DEFAULT_SENSITIVE_KEYS = frozenset({"api_key", "authorization", "password", "token"})
DEFAULT_REDACTION_PATTERNS = {
    r"(?i)\bpassword\s*[:=]\s*[^\s,;&]+",
    r"(?i)\btoken\s*[:=]\s*[^\s,;&]+",
    r"(?i)\bapi[_-]?key\s*[:=]\s*[^\s,;&]+",
    r"(?i)\bauthorization\s*[:=]\s*(?:bearer\s+)?[^\s,;&]+",
}

DEFAULT_CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(processName)s:%(process)d | %(name)s:%(funcName)s:%(lineno)d - %(message)s"

DEFAULT_FILE_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(processName)s:%(process)d | "
    "%(threadName)s:%(thread)d | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
)
