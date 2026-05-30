"""Сбор роутеров. Sprint 3: + груминг (M3)."""
from aiogram import Router

from ..modules import m0_adaptation, m3_grooming
from . import asthma, common, logging


def build_root_router() -> Router:
    root = Router()
    root.include_router(common.router)
    root.include_router(m0_adaptation.router)
    root.include_router(m3_grooming.router)
    root.include_router(logging.router)
    root.include_router(asthma.router)
    return root
