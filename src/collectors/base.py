# src/collectors/base.py
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import Any
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

RETRYABLE = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


class CollectorError(Exception):
    """Base exception for all collector failures."""


class ProviderUnavailableError(CollectorError):
    """Raised when a provider is unreachable after all retries."""


class Collector(ABC):
    """Base class for all data collectors."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        max_attempts: int = 3,
        backoff_min: float = 1.0,
        backoff_max: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._backoff_min = backoff_min
        self._backoff_max = backoff_max

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request with retry. Returns parsed JSON."""
        max_attempts = self._max_attempts
        backoff_min = self._backoff_min
        backoff_max = self._backoff_max

        @retry(
            retry=retry_if_exception_type(RETRYABLE),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(min=backoff_min, max=backoff_max),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _attempt() -> Any:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}{path}", params=params)
                response.raise_for_status()
                return response.json()

        try:
            return await _attempt()
        except Exception as exc:
            raise ProviderUnavailableError(
                f"Provider at {self._base_url}{path} unavailable after {self._max_attempts} attempts"
            ) from exc

    @abstractmethod
    async def collect(self) -> dict[str, Any]:
        """Collect all required data from this provider. Returns raw response dict."""
