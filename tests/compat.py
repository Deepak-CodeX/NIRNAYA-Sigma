"""
Minimal pytest compatibility shim for environments where pytest is not yet installed.

When pytest is installed, this module is bypassed entirely.
Enables running the test suite under standard Python without unauthorized package installs.
"""

from __future__ import annotations

import math
import re
from contextlib import contextmanager
from typing import Any, Callable, Generator, Iterable, Sequence


class ApproxNumber:
    """Approximate numerical comparison."""

    def __init__(self, expected: float, abs_tol: float = 1e-6) -> None:
        self.expected = expected
        self.abs_tol = abs_tol

    def __eq__(self, actual: object) -> bool:
        if not isinstance(actual, (int, float)):
            return False
        return math.isclose(float(actual), self.expected, abs_tol=self.abs_tol)

    def __repr__(self) -> str:
        return f"approx({self.expected} +/- {self.abs_tol})"


def approx(expected: float, abs_tol: float = 1e-6, abs: float | None = None) -> ApproxNumber:
    tol = abs if abs is not None else abs_tol
    return ApproxNumber(expected, abs_tol=tol)


class ExceptionInfo:
    def __init__(self, value: BaseException) -> None:
        self.value = value


@contextmanager
def raises(expected_exception: type[BaseException], match: str | None = None) -> Generator[ExceptionInfo, None, None]:
    """Context manager asserting that an exception is raised."""
    try:
        yield ExceptionInfo(BaseException())  # Placeholder before exception
    except expected_exception as exc:
        if match is not None:
            if not re.search(match, str(exc)):
                raise AssertionError(
                    f"Exception raised ({type(exc).__name__}: '{exc}') does not match pattern '{match}'"
                ) from exc
        return
    except BaseException as exc:
        raise AssertionError(
            f"Expected {expected_exception.__name__}, but {type(exc).__name__} was raised: {exc}"
        ) from exc
    raise AssertionError(f"Expected exception {expected_exception.__name__} was not raised")


class Mark:
    """Mock pytest.mark decorator collection."""

    @staticmethod
    def parametrize(argnames: str | Sequence[str], argvalues: Iterable[Any]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            setattr(func, "__parametrize__", (argnames, list(argvalues)))
            return func
        return decorator


def fixture(func: Callable[..., Any]) -> Callable[..., Any]:
    """Mock pytest.fixture."""
    setattr(func, "__fixture__", True)
    return func


class PytestShim:
    """Shim providing the minimal pytest surface."""
    raises = staticmethod(raises)
    approx = staticmethod(approx)
    mark = Mark
    fixture = staticmethod(fixture)


pytest = PytestShim()
