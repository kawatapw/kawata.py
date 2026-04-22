# hinaDir — Hinamizawa/AI API endpoints
# Kept separate from Loki's api.py to minimize merge conflicts.

from __future__ import annotations

from fastapi import APIRouter

from .friends import router as friends_router
from .hero_banners import router as hero_banners_router
from .most_played import router as most_played_router
from .pp_records import router as pp_records_router

router = APIRouter()
router.include_router(friends_router)
router.include_router(hero_banners_router)
router.include_router(most_played_router)
router.include_router(pp_records_router)
