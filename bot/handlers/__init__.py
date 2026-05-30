"""Роутеры хендлеров. Со Sprint 1 сюда добавятся модульные роутеры M0–M7."""
from aiogram import Router

from . import common


def build_root_router() -> Router:
    root = Router()
    root.include_router(common.router)
    # Sprint 1+: root.include_router(m0_adaptation.router) и т.д.
    return root
