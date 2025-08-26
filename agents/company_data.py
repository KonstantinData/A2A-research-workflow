"""Static company data and helper functions.

This module defines a small in‑memory dataset for a handful of well‑known
example companies.  The intent is to provide realistic looking company
information without reaching out to external services.  In a production
system these details would be resolved via API calls, web scraping or
database lookups.  Keeping the mapping here makes it easy to extend or
replace during unit testing.

Each entry contains the following keys:

``company_name``
    The canonical name of the organisation.

``company_domain``
    A domain associated with the organisation.  Where available the
    ``website`` field gives a fully qualified URL; otherwise the domain
    may be derived from the company name.

``industry``
    A human readable sector descriptor.  Classification codes are
    inferred from the description by :func:`core.classify.classify`.

``classification_number``
    A simplified industry code used in the diagrams.  The codes are
    illustrative and should not be interpreted as official NACE values.

``description``
    A short paragraph describing the organisation.  This text is passed
    through the keyword based classifier to derive classification codes.

``neighbors``
    A list of other companies that operate in a similar space.  These
    are used by the level 1 external search agent to propose related
    organisations for further research.

``customers``
    A list of names representing plausible customers of the company.  In
    a real system this information might be gleaned from invoices,
    partnerships or public announcements.  Here it is simply hard
    coded.

If a company is not present in this mapping the helper functions
produce generic fallback values based on the provided trigger.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CompanyInfo:
    company_name: str
    company_domain: str
    website: str
    industry: str
    classification_number: str
    description: str
    neighbors: List[str]
    customers: List[str]


_COMPANY_DATA: Dict[str, CompanyInfo] = {
    # Fictional manufacturing firm used in many examples
    "acme gmbh": CompanyInfo(
        company_name="Acme GmbH",
        company_domain="acme.example",
        website="https://acme.example",
        industry="manufacturing",
        classification_number="28",
        description=(
            "Acme GmbH is a fictional manufacturing company widely used as an "
            "example in documentation. It operates in the manufacturing "
            "sector, producing a broad range of industrial goods and widgets."
        ),
        neighbors=[
            "Globex Corp",
            "Initech",
            "Umbrella Corp",
            "Vehement Capital Partners",
        ],
        customers=["Umbrella Corp", "Globex Corp"],
    ),
    # Technology conglomerate
    "globex corp": CompanyInfo(
        company_name="Globex Corp",
        company_domain="globex.example",
        website="https://globex.example",
        industry="technology",
        classification_number="62.01",
        description=(
            "Globex Corp is an international technology conglomerate that "
            "provides hardware, software and consulting services. Its "
            "operations span multiple continents and it has subsidiaries "
            "in a wide range of industries."
        ),
        neighbors=[
            "Acme GmbH",
            "Initech",
            "Umbrella Corp",
            "Vehement Capital Partners",
        ],
        customers=["Initech", "Vehement Capital Partners"],
    ),
    # Fictional software company made famous by the film "Office Space"
    "initech": CompanyInfo(
        company_name="Initech",
        company_domain="initech.example",
        website="https://initech.example",
        industry="software",
        classification_number="62.01",
        description=(
            "Initech is a fictional software company specialising in "
            "enterprise information systems. It provides consulting and "
            "custom development services to large organisations."
        ),
        neighbors=[
            "Globex Corp",
            "Acme GmbH",
            "Umbrella Corp",
            "Vehement Capital Partners",
        ],
        customers=["Acme GmbH", "Vehement Capital Partners"],
    ),
    # Pharmaceutical and biotech conglomerate
    "umbrella corp": CompanyInfo(
        company_name="Umbrella Corp",
        company_domain="umbrella.example",
        website="https://umbrella.example",
        industry="pharmaceuticals",
        classification_number="21.20",
        description=(
            "Umbrella Corp is a fictional pharmaceutical and biotechnology "
            "company. It is best known for its research into advanced "
            "medical therapies and bioweapons."
        ),
        neighbors=[
            "Acme GmbH",
            "Globex Corp",
            "Initech",
            "Vehement Capital Partners",
        ],
        customers=["Globex Corp", "Initech"],
    ),
    # Private equity firm
    "vehement capital partners": CompanyInfo(
        company_name="Vehement Capital Partners",
        company_domain="vehement.example",
        website="https://vehement.example",
        industry="finance",
        classification_number="64.99",
        description=(
            "Vehement Capital Partners is a fictional private equity firm "
            "investing in a broad range of sectors. It focuses on long term "
            "investments and strategic acquisitions."
        ),
        neighbors=[
            "Acme GmbH",
            "Globex Corp",
            "Initech",
            "Umbrella Corp",
        ],
        customers=["Acme GmbH", "Umbrella Corp"],
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
    """Return neighbour company information for ``name``.

    If the company exists in the static mapping its ``neighbors`` field
    is used.  Otherwise all known companies except the one passed in are
    returned.  The helper resolves names to their :class:`CompanyInfo`
    representation.
    """
    info = lookup_company(name)
    if info:
        neighbour_names = info.neighbors
    else:
        # fallback: all other companies
        neighbour_names = [n for n in all_company_names() if n.lower() != (name or "").strip().lower()]
    neighbours: List[CompanyInfo] = []
    for neighbour_name in neighbour_names:
        n = lookup_company(neighbour_name)
        if n:
            neighbours.append(n)
    return neighbours


def customers_for(name: str) -> List[str]:
    """Return a list of customer names for ``name``.

    If the company is not present in the mapping an empty list is
    returned.  For unknown companies you may wish to consult other
    sources; here we simply return an empty list.
    """
    info = lookup_company(name)
    if info:
        return info.customers
    return []