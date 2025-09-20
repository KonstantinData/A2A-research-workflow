"""Static company data and helper functions.

This module defines a small in‑memory dataset for a handful of well‑known
example companies.  The data schema has been updated to eliminate
dependence on opaque, versioned classification numbers.  Instead each
company record includes an ``industry_group``, an ``industry`` and a
human‑readable ``description``.  An optional ``classification`` mapping
provides backward compatibility for systems that still expect NACE,
WZ2008, ÖNACE, ISIC or similar codes; however these values are no
longer required by the workflow.  Neighbouring companies and customer
lists remain available to support downstream agents.

The top‑level keys of each entry are:

``company_name``
    The canonical name of the organisation.

``company_domain``
    A domain associated with the organisation.  Where available the
    ``website`` field gives a fully qualified URL; otherwise the domain
    may be derived from the company name.

``website``
    A fully qualified URL for the company’s main web presence.  When
    not explicitly provided a default of ``https://{domain}`` is used.

``industry_group``
    A broad industry cluster such as "Manufacturing", "Technology",
    "Finance" or "Healthcare".  This value should be intuitive for
    business users and provide enough context for high‑level grouping.

``industry``
    A more specific sector or market focus (e.g. "Enterprise Software",
    "Pharmaceuticals").  It refines the ``industry_group`` for
    search and reporting purposes.

``description``
    A paragraph describing the organisation.  The description is used
    by language models and classifiers to derive additional metadata.

``classification``
    Optional mapping of classification schemes to codes.  For example
    ``{"nace": "28", "wz2008": "28"}``.  These values may be
    referenced in legacy contexts but are not required by the core
    workflow.

``neighbors``
    A list of other companies that operate in a similar space.  These
    are used by the external level 1 search agent to propose related
    organisations for further research.

``customers``
    A list of names representing plausible customers of the company.
    In a real system this information might be gleaned from invoices,
    partnerships or public announcements.  Here it is simply hard
    coded.

Helper functions are provided to look up companies by name, iterate
through all known names, and retrieve neighbour and customer lists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CompanyInfo:
    company_name: str
    company_domain: str
    website: str
    industry_group: str
    industry: str
    description: str
    neighbors: List[str] = field(default_factory=list)
    customers: List[str] = field(default_factory=list)
    classification: Optional[Dict[str, str]] = None


# Define a small static dataset for demonstration purposes.  In a real
# deployment these entries should be sourced from a database or API and
# regularly updated.  The classification mapping includes four
# commonly used schemes: NACE Rev. 2 ("nace"), the German WZ2008
# ("wz2008"), the Austrian ÖNACE ("onace") and the Swiss NOGA
# ("noga").  These codes mirror those used in the original data model
# and serve as a bridge for systems that still consume them.
# Reverse lookup for O(1) neighbor lookups
_NAME_TO_INFO: Dict[str, CompanyInfo] = {}

_COMPANY_DATA = {
    # Fictional manufacturing firm used in many examples
    "acme gmbh": CompanyInfo(
        company_name="Acme GmbH",
        company_domain="acme.example",
        website="https://acme.example",
        industry_group="Manufacturing",
        industry="Industrial Manufacturing",
        description=(
            "Acme GmbH is a fictional manufacturing company widely used as an "
            "example in documentation. It operates in the manufacturing sector, "
            "producing a broad range of industrial goods and widgets."
        ),
        neighbors=["Globex Corp", "Initech", "Umbrella Corp", "Vehement Capital Partners"],
        customers=["Umbrella Corp", "Globex Corp"],
        classification={"nace": "28", "wz2008": "28", "onace": "28", "noga": "28"},
    ),
    # Technology conglomerate
    "globex corp": CompanyInfo(
        company_name="Globex Corp",
        company_domain="globex.example",
        website="https://globex.example",
        industry_group="Technology",
        industry="Enterprise Software and Services",
        description=(
            "Globex Corp is an international technology conglomerate that "
            "provides hardware, software and consulting services. Its "
            "operations span multiple continents and it has subsidiaries "
            "in a wide range of industries."
        ),
        neighbors=["Acme GmbH", "Initech", "Umbrella Corp", "Vehement Capital Partners"],
        customers=["Initech", "Vehement Capital Partners"],
        classification={"nace": "62.01", "wz2008": "62.01", "onace": "62.01", "noga": "62.01"},
    ),
    # Fictional software company made famous by the film "Office Space"
    "initech": CompanyInfo(
        company_name="Initech",
        company_domain="initech.example",
        website="https://initech.example",
        industry_group="Technology",
        industry="Enterprise Software",
        description=(
            "Initech is a fictional software company specialising in "
            "enterprise information systems. It provides consulting and "
            "custom development services to large organisations."
        ),
        neighbors=["Globex Corp", "Acme GmbH", "Umbrella Corp", "Vehement Capital Partners"],
        customers=["Acme GmbH", "Vehement Capital Partners"],
        classification={"nace": "62.01", "wz2008": "62.01", "onace": "62.01", "noga": "62.01"},
    ),
    # Pharmaceutical and biotech conglomerate
    "umbrella corp": CompanyInfo(
        company_name="Umbrella Corp",
        company_domain="umbrella.example",
        website="https://umbrella.example",
        industry_group="Healthcare",
        industry="Pharmaceuticals and Biotechnology",
        description=(
            "Umbrella Corp is a fictional pharmaceutical and biotechnology "
            "company. It is best known for its research into advanced "
            "medical therapies and bioweapons."
        ),
        neighbors=["Acme GmbH", "Globex Corp", "Initech", "Vehement Capital Partners"],
        customers=["Globex Corp", "Initech"],
        classification={"nace": "21.20", "wz2008": "21.20", "onace": "21.20", "noga": "21.20"},
    ),
    # Private equity firm
    "vehement capital partners": CompanyInfo(
        company_name="Vehement Capital Partners",
        company_domain="vehement.example",
        website="https://vehement.example",
        industry_group="Finance",
        industry="Private Equity",
        description=(
            "Vehement Capital Partners is a fictional private equity firm "
            "investing in a broad range of sectors. It focuses on long term "
            "investments and strategic acquisitions."
        ),
        neighbors=["Acme GmbH", "Globex Corp", "Initech", "Umbrella Corp"],
        customers=["Acme GmbH", "Umbrella Corp"],
        classification={"nace": "64.99", "wz2008": "64.99", "onace": "64.99", "noga": "64.99"},
    ),
}


def lookup_company(name: str) -> Optional[CompanyInfo]:
    """Return company information for ``name`` if present.

    The lookup is case insensitive and trims whitespace.  If the company
    is not found in the static mapping ``None`` is returned.

    Parameters
    ----------
    name: str
        The name of the company to look up.

    Returns
    -------
    Optional[CompanyInfo]
        Populated :class:`CompanyInfo` instance if found, otherwise
        ``None``.
    """
    key = (name or "").strip().lower()
    return _COMPANY_DATA.get(key)


def all_company_names() -> List[str]:
    """Return a list of all known company names.

    Useful for proposing neighbour companies when the original company is
    not recognised.  The returned list contains the canonical names as
    defined in the mapping.
    """
    return [info.company_name for info in _COMPANY_DATA.values()]


def neighbours_for(name: str) -> List[CompanyInfo]:
    """Return a list of neighbouring companies for ``name``.

    The result contains the full :class:`CompanyInfo` objects for each
    neighbour.  When the company is unknown an empty list is returned.
    """
    info = lookup_company(name)
    if not info:
        return []
    
    # Initialize reverse lookup if empty
    if not _NAME_TO_INFO:
        for ci in _COMPANY_DATA.values():
            _NAME_TO_INFO[ci.company_name.lower()] = ci
    
    result = []
    for n in info.neighbors:
        ci = _NAME_TO_INFO.get(n.lower())
        if ci:
            result.append(ci)
    return result


def customers_for(name: str) -> List[str]:
    """Return a list of customer names for ``name``.

    When the company is unknown an empty list is returned.  Only the
    names are returned to reduce the need for joining against the full
    dataset.
    """
    info = lookup_company(name)
    if info:
        return list(info.customers)
    return []