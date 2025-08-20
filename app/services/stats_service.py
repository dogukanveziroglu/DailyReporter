from __future__ import annotations
from typing import Sequence, Tuple
from app.db.models import User, Report

def compute_counts(users: Sequence[User], reports: Sequence[Report]) -> Tuple[int,int]:
    return (len(users or []), len(reports or []))
