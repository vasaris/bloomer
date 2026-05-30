"""Сбор роутеров. Sprint 1: + адаптация (M0), логирование, астма-чек."""
from aiogram import Router

from ..modules import m0_adaptation
from . import asthma, common, logging


def build_root_router() -> Router:
    root = Router()
    root.include_router(common.router)
    root.include_router(m0_adaptation.router)
    root.include_router(logging.router)
    root.include_router(asthma.router)
    # Sprint 3+: активность/груминг и т.д.
    return root
