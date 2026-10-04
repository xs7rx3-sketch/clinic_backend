from enum import Enum


class NodeName(str, Enum):
    """Names of all available nodes in the AI graph."""
    GET_VALUES = "get_values"
    GET_APPOINTMENTS = "get_appointments"
    RECOMMEND_DOCTOR = "recommend_doctor"
    RESERVE_APPOINTMENT = "reserve_appointment"
    MODIFY_APPOINTMENT = "modify_appointment"
    VIP_DISPLACEMENT = "vip_displacement"
    END = "end"


class AppointmentStatus(str, Enum):
    """Allowed statuses for an Appointment."""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class AppointmentAction(str, Enum):
    """History event actions recorded in AppointmentHistory."""
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"


class PatientType(str, Enum):
    """Patient classification types."""
    NORMAL = "NORMAL"
    VIP = "VIP"


class BookingSource(str, Enum):
    """Supported booking channels."""
    AI = "AI"
    WEB = "WEB"
    MOBILE = "MOBILE"
    DASHBOARD = "DASHBOARD"
    WHATSAPP = "WHATSAPP"


class SQLReportStatus(str, Enum):
    """Status returned by the SQL Specialist node report."""
    SUCCESS = "SUCCESS"
    CONFLICT = "CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_upper = value.strip().upper()
            for member in cls:
                if member.value == val_upper or member.name == val_upper:
                    return member
        return None


class SQLActionType(str, Enum):
    """Domain action performed by the SQL Specialist."""
    LOOKUP = "lookup"
    AVAILABILITY_CHECK = "availability_check"
    RECOMMEND_DOCTOR = "recommend_doctor"
    RESERVE = "reserve"
    MODIFY = "modify"
    VIP_DISPLACEMENT = "vip_displacement"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_lower = value.strip().lower()
            for member in cls:
                if member.value == val_lower or member.name.lower() == val_lower:
                    return member
        return None


class NextRecommendedAction(str, Enum):
    """Next action recommended by the SQL specialist report."""
    RESERVE = "reserve"
    CLARIFY = "clarify"
    OFFER_ALTERNATIVES = "offer_alternatives"
    NONE = "none"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_lower = value.strip().lower()
            for member in cls:
                if member.value == val_lower or member.name.lower() == val_lower:
                    return member
        return None
