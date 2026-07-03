import enum
from typing import Literal


class OrgKind(str, enum.Enum):
    personal = "personal"
    institution = "institution"


class OrgStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class RoleName(str, enum.Enum):
    individual_learner = "individual_learner"
    instructor = "instructor"
    content_editor = "content_editor"
    org_admin = "org_admin"
    system_admin = "system_admin"


class TextFormat(str, enum.Enum):
    plain = "plain"
    markdown = "markdown"


class QuestionType(str, enum.Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    true_false = "true_false"
    scenario = "scenario"
    ordering = "ordering"
    drag_drop = "drag_drop"
    hotspot = "hotspot"


class QuestionStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    published = "published"
    needs_revision = "needs_revision"
    archived = "archived"


class LicenseStatus(str, enum.Enum):
    user_owned = "user_owned"
    third_party_licensed = "third_party_licensed"
    public_domain = "public_domain"
    unconfirmed = "unconfirmed"


class ImportFormat(str, enum.Enum):
    csv = "csv"
    xlsx = "xlsx"
    json = "json"


class ImportStatus(str, enum.Enum):
    pending = "pending"
    validating = "validating"
    previewing = "previewing"
    importing = "importing"
    completed = "completed"
    failed = "failed"
    partial = "partial"


class EtlRunPhase(str, enum.Enum):
    preview = "preview"
    committed = "committed"
    rolled_back = "rolled_back"


class QuestionFeedbackType(str, enum.Enum):
    unclear_explanation = "unclear_explanation"
    suspected_wrong_answer = "suspected_wrong_answer"
    ambiguous_stem = "ambiguous_stem"
    copyright_issue = "copyright_issue"
    other = "other"


class QuestionFeedbackStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    wont_fix = "wont_fix"


class PracticeSessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


class ExamSessionKind(str, enum.Enum):
    fixed = "fixed"
    cat = "cat"


class ExamSessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"
    aborted = "aborted"
    auto_submitted = "auto_submitted"


class MasteryLevel(str, enum.Enum):
    not_started = "not_started"
    learning = "learning"
    reviewing = "reviewing"
    mastered = "mastered"


class ErrorType(str, enum.Enum):
    concept_unclear = "concept_unclear"      # 概念不清
    misread_stem = "misread_stem"            # 审题错误
    memory_lapse = "memory_lapse"            # 记忆错误
    option_confusion = "option_confusion"    # 选项混淆
    time_pressure = "time_pressure"          # 时间压力


class AuditAction(str, enum.Enum):
    login = "login"
    logout = "logout"
    import_action = "import"
    edit = "edit"
    publish = "publish"
    delete = "delete"
    archive = "archive"
    permission_change = "permission_change"
    config_change = "config_change"
    password_reset = "password_reset"
    password_change = "password_change"


LanguageCode = Literal["en", "zh"]
LanguageMode = Literal["en", "zh", "bilingual"]
InterfaceLanguage = Literal["en", "zh"]

LANGUAGE_CODES: tuple[str, ...] = ("en", "zh")
LANGUAGE_MODES: tuple[str, ...] = ("en", "zh", "bilingual")
INTERFACE_LANGUAGES: tuple[str, ...] = ("en", "zh")
