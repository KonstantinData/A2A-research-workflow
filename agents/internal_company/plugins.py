from __future__ import annotations

"""Plugin infrastructure for internal company research sources."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type

Normalized = Dict[str, Any]
Raw = Dict[str, Any]


class InternalSource(ABC):
    """Abstract base class for internal research sources."""

    @abstractmethod
    def fetch(self, trigger: Normalized) -> Raw:
        """Retrieve raw data from the source."""

    @abstractmethod
    def normalize(self, trigger: Normalized, raw: Raw) -> Normalized:
        """Map raw data to the normalized schema."""

    def run(self, trigger: Normalized) -> Normalized:
        """Execute the source by fetching and normalizing data."""
        raw = self.fetch(trigger)
        return self.normalize(trigger, raw)


INTERNAL_SOURCES: List[InternalSource] = []


def register(source_cls: Type[InternalSource]) -> Type[InternalSource]:
    """Class decorator to register an internal source plugin."""
    INTERNAL_SOURCES.append(source_cls())
    return source_cls


from . import fetch, normalize


@register
class DefaultInternalSource(InternalSource):
    """Fallback internal source using built-in fetch and normalize."""

    def fetch(self, trigger: Normalized) -> Raw:
        return fetch.fetch(trigger)

    def normalize(self, trigger: Normalized, raw: Raw) -> Normalized:
        return normalize.normalize(trigger, raw)
