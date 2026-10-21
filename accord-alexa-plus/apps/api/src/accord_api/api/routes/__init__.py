from .agreements import router as agreements_router
from .assistant import router as assistant_router
from .assignments import router as assignments_router
from .constraints import router as constraints_router
from .demo import router as demo_router
from .drift import router as drift_router
from .expenses import router as expenses_router
from .fairness import router as fairness_router
from .mediation import router as mediation_router
from .clauses import router as clauses_router
from .alexa import router as alexa_router
from .households import router as households_router
from .interviews import router as interviews_router
from .monitoring import router as monitoring_router
from .privacy_dashboard import router as privacy_dashboard_router

__all__ = [
    "assistant_router",
    "households_router",
    "interviews_router",
    "constraints_router",
    "agreements_router",
    "assignments_router",
    "monitoring_router",
    "privacy_dashboard_router",
    "drift_router",
    "expenses_router",
    "fairness_router",
    "mediation_router",
    "clauses_router",
    "alexa_router",
    "demo_router",
]
