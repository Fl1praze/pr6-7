"""Замер поиска вакансий «до» и «после» оптимизации.

Скрипт во временной транзакции добавляет N тестовых вакансий, прогревает
статистику и выполняет один и тот же запрос дважды:

* seq scan — индексы отключены (поведение до оптимизации, O(n));
* index scan — обычный план с GIN-индексом pg_trgm (O(log n + k)).

После замеров транзакция откатывается, база остаётся без тестовых строк.

Запуск:
    .venv\\Scripts\\python.exe scripts\\benchmark_search.py --rows 20000
"""
import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

import asyncpg

# Запуск как `python scripts/benchmark_search.py` из корня проекта
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

MARKER = "BENCH_"
COUNT_SQL = """
    SELECT count(*)
    FROM vacancies
    WHERE is_archived IS NOT TRUE
      AND (title ILIKE $1 OR description ILIKE $1)
"""
PAGE_SQL = """
    SELECT id, title
    FROM vacancies
    WHERE is_archived IS NOT TRUE
      AND (title ILIKE $1 OR description ILIKE $1)
    ORDER BY id DESC
    LIMIT $2 OFFSET 0
"""


async def measure(call, repeats: int = 5) -> float:
    """Медианное время выполнения в миллисекундах."""
    timings = []
    for _ in range(repeats):
        started = time.perf_counter()
        await call()
        timings.append((time.perf_counter() - started) * 1000)
    return statistics.median(timings)


def make_rows(count: int, hr_id: int) -> list[tuple]:
    rows = []
    for i in range(count):
        # Каждая десятая вакансия подходит под запрос «Python»
        tech = "Python" if i % 10 == 0 else "Java"
        rows.append((
            f"{MARKER}{i} {tech} разработчик",
            f"{MARKER}{i} Описание вакансии: разработка сервисов на {tech}, "
            f"участие в код-ревью и проектировании.",
            80_000 + (i % 50) * 5_000,
            150_000 + (i % 50) * 5_000,
            i % 6,
            False,
            hr_id,
        ))
    return rows


async def explain(conn: asyncpg.Connection, sql: str, params: tuple) -> None:
    plan = await conn.fetch(
        f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}", *params
    )
    print("\n".join(row[0] for row in plan))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Сравнение поиска вакансий до/после индексов")
    parser.add_argument("--rows", type=int, default=20_000, help="сколько тестовых вакансий добавить")
    parser.add_argument("--query", default="Python", help="поисковый запрос")
    args = parser.parse_args()

    conn = await asyncpg.connect(
        user=settings.DB_USER,
        password=settings.DB_PASS,
        database=settings.DB_NAME,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )
    hr_id = await conn.fetchval(
        "SELECT id FROM users WHERE role IN ('hr', 'employer') ORDER BY id LIMIT 1"
    )
    if not hr_id:
        print("Нет пользователя с ролью HR — создайте его перед запуском.")
        await conn.close()
        return

    pattern = f"%{args.query}%"
    await conn.execute("BEGIN")
    try:
        before = await conn.fetchval("SELECT count(*) FROM vacancies")
        await conn.copy_records_to_table(
            "vacancies",
            records=make_rows(args.rows, hr_id),
            columns=[
                "title", "description", "salary_from", "salary_to",
                "required_experience", "is_archived", "user_id",
            ],
        )
        await conn.execute("ANALYZE vacancies")
        after = await conn.fetchval("SELECT count(*) FROM vacancies")

        print(f"Вакансий до генерации: {before}, после: {after}")
        print(f"Запрос: {args.query!r}, на страницу: 9")

        # «До»: запрещаем индексы, получаем последовательный перебор
        await conn.execute("SET LOCAL enable_seqscan = on")
        await conn.execute("SET LOCAL enable_indexscan = off")
        await conn.execute("SET LOCAL enable_bitmapscan = off")
        seq_count = await measure(lambda: conn.fetchval(COUNT_SQL, pattern))
        seq_page = await measure(lambda: conn.fetch(PAGE_SQL, pattern, 9))
        seq_total = seq_count + seq_page

        # «После»: GIN-индекс по триграммам. Seq scan отключён намеренно:
        # на небольшой таблице планировщик может предпочесть полный перебор,
        # а нам нужно измерить именно стоимость индексного пути.
        await conn.execute("SET LOCAL enable_seqscan = off")
        await conn.execute("SET LOCAL enable_indexscan = on")
        await conn.execute("SET LOCAL enable_bitmapscan = on")
        idx_count = await measure(lambda: conn.fetchval(COUNT_SQL, pattern))
        idx_page = await measure(lambda: conn.fetch(PAGE_SQL, pattern, 9))
        idx_total = idx_count + idx_page

        print("\nРезультат (медиана из 5 запусков):")
        print(f"  без индексов (seq scan): count {seq_count:.2f} мс + page {seq_page:.2f} мс = {seq_total:.2f} мс")
        print(f"  с индексами (GIN/trigram): count {idx_count:.2f} мс + page {idx_page:.2f} мс = {idx_total:.2f} мс")
        if idx_total:
            print(f"  ускорение: {seq_total / idx_total:.1f}x")

        print("\nПлан без индексов:")
        await conn.execute("SET LOCAL enable_seqscan = on")
        await conn.execute("SET LOCAL enable_indexscan = off")
        await conn.execute("SET LOCAL enable_bitmapscan = off")
        await explain(conn, PAGE_SQL, (pattern, 9))

        print("\nПлан с индексами:")
        await conn.execute("SET LOCAL enable_seqscan = off")
        await conn.execute("SET LOCAL enable_indexscan = on")
        await conn.execute("SET LOCAL enable_bitmapscan = on")
        await explain(conn, PAGE_SQL, (pattern, 9))
    finally:
        await conn.execute("ROLLBACK")
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
