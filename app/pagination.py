"""Общие структуры для постраничного вывода.

PageParams принимает номер страницы и размер страницы из query-параметров,
Page — типизированный ответ API со списком элементов и метаданными.
"""
from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(1, ge=1, description="Номер страницы, начиная с 1")
    page_size: int = Field(9, ge=1, le=50, description="Количество записей на странице")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
    has_prev: bool
    has_next: bool

    @classmethod
    def create(cls, items: list[T], total: int, page: int, page_size: int) -> "Page[T]":
        pages = max(1, ceil(total / page_size)) if total else 1
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            has_prev=page > 1,
            has_next=page < pages,
        )


def clamp_page(page: int, total: int, page_size: int) -> int:
    """Не даёт уйти на несуществующую страницу после удаления записей."""
    pages = max(1, ceil(total / page_size)) if total else 1
    return min(max(page, 1), pages)
