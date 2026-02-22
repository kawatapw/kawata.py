# hinaDir — Hinamizawa/AI API endpoints
# Kept separate from Loki's api.py to minimize merge conflicts.

from __future__ import annotations

from fastapi import APIRouter

from .friends import router as friends_router

router = APIRouter()
router.include_router(friends_router)
