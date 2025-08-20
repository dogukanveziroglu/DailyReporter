from __future__ import annotations
import uuid, pandas as pd
from typing import Sequence
from app.db.models import Report

def export_reports_dataframe(reports: Sequence[Report]) -> str:
    """Raporları CSV dosyasına yazar ve dosya yolunu döner."""
    rows = []
    for r in reports:
        rows.append({"user_id": r.user_id, "date": str(r.date), "project": r.project or "", "content": r.content})
    df = pd.DataFrame(rows)
    path = f"data/reports_{uuid.uuid4().hex[:8]}.csv"
    df.to_csv(path, index=False, encoding="utf-8")
    return path
