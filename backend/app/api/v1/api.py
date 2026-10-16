from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.organizations import router as org_router
from app.api.v1.contracts import router as contracts_router
from app.api.v1.obligations import router as obligations_router
from app.api.v1.vendors import router as vendors_router
from app.api.v1.playbook import router as playbook_router
from app.api.v1.ai import router as ai_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.notes import router as notes_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.lawyers import router as lawyers_router
from app.api.v1.matters import router as matters_router
from app.api.v1.platform import router as platform_router
from app.api.v1.data_management import router as data_management_router
from app.api.v1.activity import router as activity_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(org_router)
api_router.include_router(contracts_router)
api_router.include_router(obligations_router)
api_router.include_router(vendors_router)
api_router.include_router(playbook_router)
api_router.include_router(ai_router)
api_router.include_router(calendar_router)
api_router.include_router(notes_router)
api_router.include_router(tasks_router)
api_router.include_router(notifications_router)
api_router.include_router(lawyers_router)
api_router.include_router(matters_router)
api_router.include_router(platform_router)
api_router.include_router(data_management_router)
api_router.include_router(activity_router)

