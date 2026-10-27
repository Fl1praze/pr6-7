"""Optimize vacancy search: composite and trigram indexes

Revision ID: a7c1e9d4b2f0
Revises: 320e164d7a07
Create Date: 2026-10-20 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7c1e9d4b2f0'
down_revision: Union[str, Sequence[str], None] = '320e164d7a07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Индексы под основные запросы списка вакансий.

    Составные индексы закрывают фильтры «активные + сортировка по id»
    и «вакансии конкретного HR + архивность». GIN-индекс по триграммам
    ускоряет ILIKE '%...%' в заголовке и описании.
    """
    op.create_index(
        "ix_vacancies_archive_id",
        "vacancies",
        ["is_archived", "id"],
        unique=False,
    )
    op.create_index(
        "ix_vacancies_user_archive_id",
        "vacancies",
        ["user_id", "is_archived", "id"],
        unique=False,
    )
    op.create_index(
        "ix_vacancies_experience",
        "vacancies",
        ["required_experience"],
        unique=False,
    )

    # pg_trgm — доверенное расширение PostgreSQL 13+, но на старых серверах
    # или без прав может быть недоступно. Тогда поиск продолжит работать
    # без GIN-индекса, просто медленнее.
    op.execute("""
        DO $$
        BEGIN
            BEGIN
                EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_trgm';
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'pg_trgm недоступен: %', SQLERRM;
            END;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
                EXECUTE 'CREATE INDEX IF NOT EXISTS ix_vacancies_title_trgm '
                        'ON vacancies USING gin (title gin_trgm_ops)';
                EXECUTE 'CREATE INDEX IF NOT EXISTS ix_vacancies_description_trgm '
                        'ON vacancies USING gin (description gin_trgm_ops)';
            ELSE
                RAISE NOTICE 'Индексы pg_trgm пропущены';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Удаляем только созданные индексы, расширение не трогаем."""
    op.execute("DROP INDEX IF EXISTS ix_vacancies_description_trgm")
    op.execute("DROP INDEX IF EXISTS ix_vacancies_title_trgm")
    op.drop_index("ix_vacancies_experience", table_name="vacancies")
    op.drop_index("ix_vacancies_user_archive_id", table_name="vacancies")
    op.drop_index("ix_vacancies_archive_id", table_name="vacancies")
