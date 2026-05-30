"""Сбор роутеров. Sprint 4: + M5 тренинг/трюфели."""
from aiogram import Router

from ..modules import m0_adaptation, m3_grooming, m5_training
from . import asthma, common, logging


def build_root_router() -> Router:
    root = Router()
    root.include_router(common.router)
    root.include_router(m0_adaptation.router)
    root.include_router(m3_grooming.router)
    root.include_router(m5_training.router)
    root.include_router(logging.router)
    root.include_router(asthma.router)
    return root
