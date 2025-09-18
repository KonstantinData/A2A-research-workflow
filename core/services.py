"""Service layer for external integrations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from core.circuit_breaker import with_circuit_breaker
from core.utils import log_step


class ExternalService(ABC):
    """Base class for external service integrations."""
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if service is available."""
        pass
    
    @abstractmethod
    def get_service_name(self) -> str:
        """Get service name for logging."""
        pass


class GoogleCalendarService(ExternalService):
    """Service wrapper for Google Calendar integration."""
    
    def __init__(self):
        self._calendar_module = None
        try:
            from integrations import google_calendar
            self._calendar_module = google_calendar
        except ImportError:
            pass
    
    def is_available(self) -> bool:
        """Check if Google Calendar service is available."""
        return self._calendar_module is not None
    
    def get_service_name(self) -> str:
        return "google_calendar"
    
    @with_circuit_breaker("google_calendar", failure_threshold=3, recovery_timeout=60)
    def fetch_events(self) -> List[Dict[str, Any]]:
        """Fetch calendar events with circuit breaker protection."""
        if not self.is_available():
            log_step("service", "unavailable", {"service": self.get_service_name()}, severity="warning")
            return []
        
        try:
            return self._calendar_module.fetch_events()
        except Exception as e:
            log_step("service", "fetch_failed", {
                "service": self.get_service_name(),
                "error": str(e)
            }, severity="error")
            raise





class EmailService(ExternalService):
    """Service wrapper for email integration."""
    
    def __init__(self):
        self._email_module = None
        try:
            from integrations import email_sender
            self._email_module = email_sender
        except ImportError:
            pass
    
    def is_available(self) -> bool:
        """Check if email service is available."""
        return self._email_module is not None
    
    def get_service_name(self) -> str:
        return "email"
    
    @with_circuit_breaker("email", failure_threshold=2, recovery_timeout=30)
    def send_email(self, **kwargs: Any) -> None:
        """Send email with circuit breaker protection."""
        if not self.is_available():
            log_step("service", "unavailable", {"service": self.get_service_name()}, severity="warning")
            return
        
        try:
            self._email_module.send_email(**kwargs)
        except Exception as e:
            log_step("service", "send_failed", {
                "service": self.get_service_name(),
                "error": str(e)
            }, severity="error")
            raise


# Service instances
google_calendar_service = GoogleCalendarService()
email_service = EmailService()