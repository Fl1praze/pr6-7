import pytest
from pydantic import ValidationError

from app.pagination import Page, clamp_page
from app.vacancies.dao import escape_like
from app.vacancies.schemas import SVacancyFilter


def test_empty_page_has_one_page():
    page = Page.create([], 0, 1, 9)

    assert page.items == []
    assert page.total == 0
    assert page.pages == 1
    assert page.has_prev is False
    assert page.has_next is False


def test_page_metadata():
    page = Page.create(list(range(9)), 25, 2, 9)

    assert page.total == 25
    assert page.pages == 3
    assert page.page == 2
    assert page.has_prev is True
    assert page.has_next is True


def test_last_page_has_no_next():
    page = Page.create([1], 25, 3, 9)

    assert page.has_prev is True
    assert page.has_next is False


@pytest.mark.parametrize(
    "requested, expected",
    [(0, 1), (1, 1), (3, 3), (99, 3)],
)
def test_clamp_page(requested, expected):
    assert clamp_page(requested, total=25, page_size=9) == expected


def test_escape_like():
    assert escape_like("50%_off\\") == "50\\%\\_off\\\\"


def test_filter_rejects_inverted_salary_range():
    with pytest.raises(ValidationError):
        SVacancyFilter(salary_from=100_000, salary_to=50_000)


def test_filter_accepts_blank_values():
    filters = SVacancyFilter(salary_from="", salary_to="", max_experience="")

    assert filters.salary_from is None
    assert filters.salary_to is None
    assert filters.max_experience is None
    assert filters.page == 1
    assert filters.sort == "new"
