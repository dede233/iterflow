from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    LOCKED = "LOCKED"


class DataScope(StrEnum):
    SELF = "SELF"
    # Reserved for a future organization/team model. V1.5 APIs reject this value.
    TEAM = "TEAM"
    ALL = "ALL"


class FeedbackType(StrEnum):
    NEW_FEATURE = "NEW_FEATURE"
    FEATURE_OPTIMIZATION = "FEATURE_OPTIMIZATION"
    SYSTEM_ISSUE = "SYSTEM_ISSUE"
    DATA_ISSUE = "DATA_ISSUE"
    UI_UX = "UI_UX"
    OTHER = "OTHER"


class FeedbackUrgency(StrEnum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"


class FeedbackStatus(StrEnum):
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    REQUIREMENT_LINKED = "REQUIREMENT_LINKED"
    PLANNED = "PLANNED"
    DEVELOPING = "DEVELOPING"
    TESTING = "TESTING"
    ONLINE = "ONLINE"
    DUPLICATE = "DUPLICATE"
    CANNOT_REPRODUCE = "CANNOT_REPRODUCE"
    CLOSED = "CLOSED"


class ManualFeedbackStatus(StrEnum):
    """Feedback statuses a human may set through the status API.

    Downstream statuses (REQUIREMENT_LINKED / PLANNED / DEVELOPING / TESTING /
    ONLINE) are produced only by convert / version / publish transactions and are
    intentionally excluded here so they can never be set by hand.
    """

    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    CANNOT_REPRODUCE = "CANNOT_REPRODUCE"
    CLOSED = "CLOSED"


class RequirementStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    PLANNED = "PLANNED"
    DEVELOPING = "DEVELOPING"
    TESTING = "TESTING"
    DONE = "DONE"
    ONLINE = "ONLINE"
    PAUSED = "PAUSED"
    CANCELED = "CANCELED"


class ManualRequirementStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    PLANNED = "PLANNED"
    DEVELOPING = "DEVELOPING"
    TESTING = "TESTING"
    DONE = "DONE"
    PAUSED = "PAUSED"
    CANCELED = "CANCELED"


class RequirementSource(StrEnum):
    DIRECT = "DIRECT"
    FEEDBACK = "FEEDBACK"


class FeedbackConvertType(StrEnum):
    """How a Feedback is turned into / attached to a Requirement (Phase 4)."""

    CREATE_NEW = "CREATE_NEW"
    LINK_EXISTING = "LINK_EXISTING"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class VersionStatus(StrEnum):
    PLANNING = "PLANNING"
    DEVELOPING = "DEVELOPING"
    TESTING = "TESTING"
    READY = "READY"
    RELEASED = "RELEASED"
    CANCELED = "CANCELED"


class ManualVersionStatus(StrEnum):
    PLANNING = "PLANNING"
    DEVELOPING = "DEVELOPING"
    TESTING = "TESTING"
    READY = "READY"
    CANCELED = "CANCELED"


class ReleaseResult(StrEnum):
    SUCCESS = "SUCCESS"


class StorageDriver(StrEnum):
    LOCAL = "LOCAL"
    S3 = "S3"


class NotificationType(StrEnum):
    SYSTEM = "SYSTEM"
    FEEDBACK = "FEEDBACK"
    REQUIREMENT = "REQUIREMENT"
    VERSION = "VERSION"
    RELEASE = "RELEASE"


class EditingEntityType(StrEnum):
    FEEDBACK = "FEEDBACK"
    REQUIREMENT = "REQUIREMENT"
    VERSION = "VERSION"
