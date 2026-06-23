"""Model registry. Importing this package registers all tables on Base.metadata
so Alembic autogenerate and Base.metadata.create_all see every table.
"""

from app.models.admin import AuditLog, CatParamsVersion, SchemaMeta  # noqa: F401
from app.models.auth import (  # noqa: F401
    Class,
    ClassMembership,
    Organization,
    OrganizationMembership,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.models.exam import ExamAnswer, ExamSession  # noqa: F401
from app.models.practice import (  # noqa: F401
    PracticeAnswer,
    PracticeSession,
    UserQuestionState,
)
from app.models.question import (  # noqa: F401
    Book,
    Chapter,
    Explanation,
    ImportJob,
    Question,
    QuestionFeedback,
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
)
from app.models.etl import (  # noqa: F401
    ChapterDomainMapping,
    EtlDataset,
    EtlRun,
    QuestionExternalKey,
)
from app.models.taxonomy import (  # noqa: F401
    ExamBlueprint,
    ExamDomain,
    KnowledgePoint,
    KnowledgePointDomain,
    Tag,
)

__all__ = [
    "Organization",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "OrganizationMembership",
    "Class",
    "ClassMembership",
    "ExamBlueprint",
    "ExamDomain",
    "KnowledgePoint",
    "KnowledgePointDomain",
    "Tag",
    "Book",
    "Chapter",
    "Question",
    "QuestionOption",
    "Explanation",
    "QuestionMapping",
    "QuestionRevision",
    "QuestionFeedback",
    "ImportJob",
    "PracticeSession",
    "PracticeAnswer",
    "UserQuestionState",
    "ExamSession",
    "ExamAnswer",
    "AuditLog",
    "SchemaMeta",
    "CatParamsVersion",
    "EtlDataset",
    "EtlRun",
    "QuestionExternalKey",
    "ChapterDomainMapping",
]
