from fastapi import APIRouter
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.users import router as users_router
from backend.app.api.v1.teams import router as teams_router
from backend.app.api.v1.leads import router as leads_router
from backend.app.api.v1.properties import router as properties_router
from backend.app.api.v1.activities import router as activities_router
from backend.app.api.v1.followups import router as followups_router
from backend.app.api.v1.appointments import router as appointments_router
from backend.app.api.v1.transfers import router as transfers_router
from backend.app.api.v1.dashboard import router as dashboard_router
from backend.app.api.v1.reports import router as reports_router
from backend.app.api.v1.notifications import router as notifications_router
from backend.app.api.v1.voice import router as voice_router
from backend.app.api.v1.ai import router as ai_router
from backend.app.api.v1.agents import router as agents_router
from backend.app.api.v1.conversations import router as conversations_router
from backend.app.api.v1.locations import router as locations_router
from backend.app.api.v1.calendar import router as calendar_router
from backend.app.api.v1.property_offers import router as property_offers_router
from backend.app.api.v1.marketing import router as marketing_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(teams_router)
api_router.include_router(agents_router)
api_router.include_router(conversations_router)
api_router.include_router(locations_router)
api_router.include_router(calendar_router)
api_router.include_router(property_offers_router)
api_router.include_router(leads_router)
api_router.include_router(properties_router)
api_router.include_router(activities_router)
api_router.include_router(followups_router)
api_router.include_router(appointments_router)
api_router.include_router(transfers_router)
api_router.include_router(dashboard_router)
api_router.include_router(reports_router)
api_router.include_router(notifications_router)
api_router.include_router(voice_router)
api_router.include_router(ai_router)
api_router.include_router(marketing_router)
