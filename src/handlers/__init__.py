from aiogram import Router
from .start import router as start_router
from .quiz import router as quiz_router
from .stats import router as stats_router
from .multiplayer import router as multiplayer_router

router = Router()
router.include_router(start_router)
router.include_router(quiz_router)
router.include_router(stats_router)
router.include_router(multiplayer_router)
