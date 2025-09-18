"""Circuit breaker pattern for external API resilience."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field

from core.utils import log_step


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker for external service calls."""
    
    failure_threshold: int = 5
    recovery_timeout: int = 60
    expected_exception: type = Exception
    
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: Optional[float] = field(default=None, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    
    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection."""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                log_step("circuit_breaker", "half_open", {"service": func.__name__})
            else:
                raise Exception(f"Circuit breaker OPEN for {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            self._on_success(func.__name__)
            return result
        except self.expected_exception as e:
            self._on_failure(func.__name__, str(e))
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self._last_failure_time is not None and
            time.time() - self._last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self, service_name: str) -> None:
        """Handle successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            log_step("circuit_breaker", "closed", {"service": service_name})
        self._failure_count = 0
    
    def _on_failure(self, service_name: str, error: str) -> None:
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            log_step("circuit_breaker", "opened", {
                "service": service_name,
                "failure_count": self._failure_count,
                "error": error
            }, severity="warning")


# Global circuit breakers for different services
_CIRCUIT_BREAKERS: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(service_name: str, **kwargs: Any) -> CircuitBreaker:
    """Get or create circuit breaker for a service."""
    if service_name not in _CIRCUIT_BREAKERS:
        _CIRCUIT_BREAKERS[service_name] = CircuitBreaker(**kwargs)
    return _CIRCUIT_BREAKERS[service_name]


def with_circuit_breaker(service_name: str, **breaker_kwargs: Any):
    """Decorator to add circuit breaker protection to a function."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            breaker = get_circuit_breaker(service_name, **breaker_kwargs)
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator