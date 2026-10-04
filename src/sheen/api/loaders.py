"""DataLoaders: batch per-spill lookups into one query per request.

Without these, listing 50 spills with their issues would run 51 queries.
A fresh set is created per request so nothing is cached across requests.
"""

from collections import defaultdict
from dataclasses import dataclass

from psycopg.rows import DictRow
from strawberry.dataloader import DataLoader

from sheen.api import db


async def _issues(ids: list[str]) -> list[list[DictRow]]:
    rows = await db.fetch(
        """SELECT spill_id, code, severity, field, message, details
           FROM clean.spill_issues WHERE spill_id = ANY(%s)
           ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, code""",
        (ids,),
    )
    by_id: dict[str, list[DictRow]] = defaultdict(list)
    for r in rows:
        by_id[r["spill_id"]].append(r)
    return [by_id.get(i, []) for i in ids]


async def _exposure(ids: list[str]) -> list[DictRow | None]:
    rows = await db.fetch("SELECT * FROM analysis.spill_exposure WHERE spill_id = ANY(%s)", (ids,))
    by_id = {r["spill_id"]: r for r in rows}
    return [by_id.get(i) for i in ids]


async def _areas(pcodes: list[str]) -> list[DictRow | None]:
    rows = await db.fetch(
        """SELECT a.pcode, a.name, a.level, s.name AS state_name, a.state_code
           FROM ref.admin_areas a LEFT JOIN ref.admin_areas s ON s.pcode = a.parent_pcode
           WHERE a.pcode = ANY(%s)""",
        (pcodes,),
    )
    by_id = {r["pcode"]: r for r in rows}
    return [by_id.get(p) for p in pcodes]


@dataclass
class Loaders:
    issues: DataLoader[str, list[DictRow]]
    exposure: DataLoader[str, DictRow | None]
    areas: DataLoader[str, DictRow | None]


def make_loaders() -> Loaders:
    return Loaders(
        issues=DataLoader(load_fn=_issues),
        exposure=DataLoader(load_fn=_exposure),
        areas=DataLoader(load_fn=_areas),
    )
