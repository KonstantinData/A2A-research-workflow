"""Field completion agent with structured extraction strategies."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

from core.utils import log_step

try:
    import openai
except ImportError:
    openai = None


@dataclass
class ExtractionResult:
    """Structured result from field extraction."""
    company_name: Optional[str] = None
    domain: Optional[str] = None
    confidence: float = 0.0
    method: str = "unknown"
    raw_text: str = ""


class FieldExtractor(Protocol):
    """Protocol for field extraction strategies."""
    
    def extract(self, text: str, payload: Dict[str, Any]) -> ExtractionResult:
        """Extract company fields from text and payload."""
        ...


class OpenAIExtractor:
    """OpenAI-based field extraction."""
    
    def __init__(self):
        self.client = None
        if openai and os.getenv("OPENAI_API_KEY"):
            self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def extract(self, text: str, payload: Dict[str, Any]) -> ExtractionResult:
        """Extract fields using OpenAI API."""
        if not self.client or not text.strip():
            return ExtractionResult(method="openai_unavailable")
        
        prompt = (
            "Extract company information from the following text. "
            "Return a JSON object with 'company_name' (official company name) "
            "and 'domain' (web domain without protocol). "
            "If information is unclear or missing, use null values.\n\n"
            f"Text: {text}"
        )
        
        try:
            response = self.client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": "You are a precise data extraction assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            content = response.choices[0].message.content
            if not content:
                return ExtractionResult(method="openai_empty_response")
            
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return ExtractionResult(method="openai_json_error")
            
            if not isinstance(data, dict):
                return ExtractionResult(method="openai_invalid_format")
            return ExtractionResult(
                company_name=data.get("company_name"),
                domain=data.get("domain"),
                confidence=0.8,
                method="openai",
                raw_text=text
            )
        except Exception as e:
            log_step(
                "field_completion", 
                "openai_error", 
                {"error": str(e), "text_length": len(text)},
                severity="warning"
            )
            return ExtractionResult(method="openai_error")


class RegexExtractor:
    """Regex-based field extraction with multiple strategies."""
    
    def __init__(self):
        # Pre-compile regex patterns for performance
        self.COMPILED_COMPANY_PATTERNS = [
            # Formal company suffixes
            re.compile(r"\b([A-Z][A-Za-z0-9&.\s\-]*(?:GmbH|AG|KG|SE|Ltd|Inc|LLC|Corp|Company|Co\.|Group|Solutions|Technologies|Tech|Systems|Services))\b"),
            # Meeting/call contexts
            re.compile(r"(?:Meeting|Call|Visit|Discussion)\s+(?:with|at|to)\s+([A-Z][A-Za-z0-9&.\s\-]{2,30})(?:\s|$|[,.;])"),
            # Project/client contexts
            re.compile(r"(?:Project|Client|Customer)\s*:?\s*([A-Z][A-Za-z0-9&.\s\-]{2,30})(?:\s|$|[,.;])"),
            # Capitalized sequences (2-4 words)
            re.compile(r"\b([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*){1,3})\b")
        ]
        
        self.COMPILED_DOMAIN_PATTERNS = [
            re.compile(r"\b([a-z0-9\-]+\.[a-z]{2,})(?:/[^\s]*)?\b", re.IGNORECASE),
            re.compile(r"(?:https?://)([a-z0-9\-]+\.[a-z]{2,})(?:/[^\s]*)?", re.IGNORECASE),
            re.compile(r"(?:www\.)([a-z0-9\-]+\.[a-z]{2,})(?:/[^\s]*)?", re.IGNORECASE)
        ]
    
    def extract(self, text: str, payload: Dict[str, Any]) -> ExtractionResult:
        """Extract fields using regex patterns."""
        result = ExtractionResult(method="regex", raw_text=text)
        
        # Extract company name
        company_name = self._extract_company_name(text)
        if company_name:
            result.company_name = company_name
            result.confidence = 0.6
        
        # Extract domain
        domain = self._extract_domain(text, payload)
        if domain:
            result.domain = domain
            if result.confidence == 0.0:
                result.confidence = 0.4
        
        return result
    
    def _extract_company_name(self, text: str) -> Optional[str]:
        """Extract company name using multiple patterns."""
        for pattern in self.COMPILED_COMPANY_PATTERNS:
            matches = pattern.finditer(text)
            for match in matches:
                candidate = match.group(1).strip()
                if self._is_valid_company_name(candidate):
                    return candidate  # Early termination for performance
        return None
    
    def _extract_domain(self, text: str, payload: Dict[str, Any]) -> Optional[str]:
        """Extract domain from text or email addresses."""
        # Try direct domain extraction from text
        for pattern in self.COMPILED_DOMAIN_PATTERNS:
            match = pattern.search(text)
            if match:
                domain = match.group(1).lower().rstrip("/")
                if self._is_valid_domain(domain):
                    return domain
        
        # Fallback to email domain extraction
        return self._extract_domain_from_emails(payload)
    
    def _extract_domain_from_emails(self, payload: Dict[str, Any]) -> Optional[str]:
        """Extract domain from email addresses in payload."""
        emails = []
        
        # Collect emails from various sources
        for key in ("creatorEmail", "creator", "email"):
            val = payload.get(key)
            if isinstance(val, dict):
                val = val.get("email")
            if val and isinstance(val, str):
                emails.append(val)
        
        for attendee in payload.get("attendees", []):
            if isinstance(attendee, dict) and attendee.get("email"):
                emails.append(attendee["email"])
        
        # Extract domain from first valid business email
        for email in emails:
            if "@" in email:
                parts = email.split("@")
                if len(parts) == 2:  # Validate email format
                    domain = parts[1].lower()
                    if self._is_business_domain(domain):
                        return domain
        
        return None
    
    def _is_valid_company_name(self, name: str) -> bool:
        """Validate extracted company name."""
        if not name or len(name) < 2 or len(name) > 100:
            return False
        
        # Filter out common false positives
        false_positives = {
            "Meeting", "Call", "Visit", "Discussion", "Project", "Client",
            "Customer", "Team", "Department", "Office", "Building"
        }
        return name not in false_positives
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Validate extracted domain with improved checks."""
        if not domain or "." not in domain or len(domain) < 4:
            return False
        
        # Enhanced domain validation
        parts = domain.split(".")
        if len(parts) < 2:
            return False
        
        # Check each part has minimum length and valid characters
        for part in parts:
            if len(part) < 1 or not (part.replace("-", "").isalnum()):
                return False
            if part.startswith("-") or part.endswith("-"):
                return False
        
        # TLD should be at least 2 characters
        return len(parts[-1]) >= 2
    
    def _is_business_domain(self, domain: str) -> bool:
        """Check if domain appears to be a business domain."""
        if not self._is_valid_domain(domain):
            return False
        
        # Filter out common personal email providers
        personal_domains = {
            "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
            "icloud.com", "aol.com", "web.de", "gmx.de"
        }
        return domain.lower() not in personal_domains


def _collect_text(trigger: Dict[str, Any]) -> str:
    """Collect all relevant text from trigger payload."""
    payload = trigger.get("payload", {})
    text_parts = []
    
    # Primary text fields
    for field in ("summary", "description", "notes", "title", "subject"):
        value = payload.get(field)
        if value and isinstance(value, str):
            text_parts.append(value.strip())
    
    # Contact notes
    for contact in payload.get("contacts", []):
        if isinstance(contact, dict) and contact.get("notes"):
            text_parts.append(contact["notes"].strip())
    
    # Location information
    location = payload.get("location")
    if location and isinstance(location, str):
        text_parts.append(location.strip())
    
    return "\n".join(filter(None, text_parts))


def run(trigger: Dict[str, Any]) -> Dict[str, Any]:
    """Extract missing company fields using multiple strategies.
    
    Args:
        trigger: Event or contact trigger containing payload data
        
    Returns:
        Dictionary with extracted company_name and/or domain fields
    """
    text = _collect_text(trigger)
    payload = trigger.get("payload", {})
    
    if not text.strip():
        log_step(
            "field_completion",
            "no_text_available",
            {"payload_keys": list(payload.keys())},
            severity="warning"
        )
        return {}
    
    # Use cached extractors for performance
    if not hasattr(run, '_extractors'):
        run._extractors = [OpenAIExtractor(), RegexExtractor()]
    
    best_result = ExtractionResult()
    
    for extractor in extractors:
        try:
            result = extractor.extract(text, payload)
            
            # Log extraction attempt
            log_step(
                "field_completion",
                "extraction_attempt",
                {
                    "method": result.method,
                    "confidence": result.confidence,
                    "found_company": bool(result.company_name),
                    "found_domain": bool(result.domain),
                    "text_length": len(text)
                }
            )
            
            # Use result if it's better than current best
            if result.confidence > best_result.confidence:
                best_result = result
                
                # If we have high confidence, stop trying
                if result.confidence >= 0.8:
                    break
                    
        except Exception as e:
            log_step(
                "field_completion",
                "extraction_error",
                {"method": extractor.__class__.__name__, "error": str(e)},
                severity="error"
            )
    
    # Build final result
    final_result = {}
    if best_result.company_name:
        final_result["company_name"] = best_result.company_name
    if best_result.domain:
        final_result["domain"] = best_result.domain
    
    # Log final outcome
    log_step(
        "field_completion",
        "extraction_complete",
        {
            "method": best_result.method,
            "confidence": best_result.confidence,
            "fields_extracted": list(final_result.keys()),
            "success": bool(final_result)
        }
    )
    
    return final_result


__all__ = ["run", "ExtractionResult", "OpenAIExtractor", "RegexExtractor"]
