# agents/internal_company/plugins.py
from __future__ import annotations

"""Plugin infrastructure for internal company research sources."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type

Normalized = Dict[str, Any]
Raw = Dict[str, Any]


class InternalSource(ABC):
    @abstractmethod
    def fetch(self, trigger: Normalized) -> Raw: ...
    @abstractmethod
    def normalize(self, trigger: Normalized, raw: Raw) -> Normalized: ...

    def run(self, trigger: Normalized) -> Normalized:
        raw = self.fetch(trigger)
        return self.normalize(trigger, raw)


INTERNAL_SOURCES: List[InternalSource] = []


def register(source_cls: Type[InternalSource]) -> Type[InternalSource]:
    INTERNAL_SOURCES.append(source_cls())
    return source_cls


from . import fetch, normalize


@register
class DefaultInternalSource(InternalSource):
    def fetch(self, trigger: Normalized) -> Raw:
        return fetch.fetch(trigger)

    def normalize(self, trigger: Normalized, raw: Raw) -> Normalized:
        return normalize.normalize(trigger, raw)
