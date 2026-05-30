"""Сбор роутеров. Sprint 6: + M6 социализация, M7 путешествия."""
from aiogram import Router

from ..modules import (
    m0_adaptation,
    m3_grooming,
    m4_health,
    m5_training,
    m6_socialization,
    m7_travel,
)
from . import asthma, common, logging


def build_root_router() -> Router:
    root = Router()
    root.include_router(common.router)
    root.include_router(m0_adaptation.router)
    root.include_router(m3_grooming.router)
    root.include_router(m4_health.router)
    root.include_router(m5_training.router)
    root.include_router(m6_socialization.router)
    root.include_router(m7_travel.router)
    root.include_router(logging.router)
    root.include_router(asthma.router)
    return root
