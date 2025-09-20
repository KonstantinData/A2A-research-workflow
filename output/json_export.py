"""JSON export functionality for A2A workflow."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from config.settings import SETTINGS


def export_json(rows: List[Dict[str, Any]], out_path: Optional[Path] = None) -> Path:
    """Export data as JSON with required format.
    
    Each exported object includes:
    - id (string, unique)
    - timestamp (ISO 8601)
    - data (object with exported content)
    
    Args:
        rows: List of data rows to export
        out_path: Output file path (defaults to exports/data.json)
        
    Returns:
        Path to the exported JSON file
    """
    if out_path is None:
        out_path = SETTINGS.exports_dir / "data.json"
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert rows to required JSON format
    exported_objects = []
    for row in rows or []:
        # Generate unique ID for each row
        row_id = row.get("id") or str(uuid.uuid4())
        
        # Use existing timestamp or generate new one
        timestamp = row.get("timestamp")
        if not timestamp:
            timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        elif isinstance(timestamp, datetime):
            timestamp = timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        
        # Create data object excluding id and timestamp
        data = {k: v for k, v in row.items() if k not in ("id", "timestamp")}
        
        exported_objects.append({
            "id": row_id,
            "timestamp": timestamp,
            "data": data
        })
    
    # Sort by timestamp
    exported_objects.sort(key=lambda x: x["timestamp"])
    
    # Remove duplicates based on ID (keep first occurrence)
    seen_ids = set()
    unique_objects = []
    for obj in exported_objects:
        if obj["id"] not in seen_ids:
            unique_objects.append(obj)
            seen_ids.add(obj["id"])
    
    # Write JSON file
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(unique_objects, fh, ensure_ascii=False, indent=2)
    
    return out_path