#!/usr/bin/env python3
"""Test PDF generation functionality."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from output.pdf_render import render_pdf
from output.csv_export import export_csv


def test_pdf_generation():
    """Test PDF and CSV generation."""
    
    # Sample data
    sample_data = [
        {
            "company_name": "Example GmbH",
            "domain": "example.com",
            "industry_group": "Technology",
            "industry": "Software Development",
            "description": "Leading software company",
            "country": "DE"
        }
    ]
    
    fields = ["company_name", "domain", "industry_group", "industry", "description", "country"]
    meta = {"title": "A2A Research Report", "generated_at": "2025-09-20"}
    
    try:
        # Generate PDF
        pdf_path = render_pdf(
            rows=sample_data,
            fields=fields,
            meta=meta
        )
        print(f"✓ PDF generated successfully: {pdf_path}")
        
        # Generate CSV
        csv_path = export_csv(sample_data)
        print(f"✓ CSV generated successfully: {csv_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ PDF/CSV generation failed: {e}")
        return False


if __name__ == "__main__":
    success = test_pdf_generation()
    sys.exit(0 if success else 1)