# isort: dont-add-imports

from fastapi import APIRouter

from .api import router
from .hinaDir import router as hina_router

apiv1_router: APIRouter = APIRouter(tags=["API v1"], prefix="/v1")

apiv1_router.include_router(router)
apiv1_router.include_router(hina_router)
