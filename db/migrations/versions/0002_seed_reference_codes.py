"""seed reference codes and states

Code labels are taken from the Nigerian Oil Spill Monitor map legend
(oilspillmonitor.ng, js/index bundle). 'gs' and 'mys' appear in the data but
not in the legend; they are labelled as unknown rather than guessed.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CODES = {
    "cause": {
        "sab": "sabotage/theft",
        "eqf": "equipment failure",
        "cor": "corrosion",
        "ome": "operational/maintenance error",
        "ytd": "yet to determine",
        "mys": "unknown (not in source legend)",
        "other": "other",
    },
    "contaminant": {
        "cr": "crude oil",
        "ga": "gas",
        "re": "refined products",
        "co": "condensate",
        "ch": "chemicals, drilling mud",
        "no": "no spill",
        "gs": "unknown (not in source legend)",
        "other": "other",
    },
    "habitat": {
        "la": "land",
        "sw": "swamp",
        "ss": "seasonal swamp",
        "iw": "inland waters",
        "ns": "near shore",
        "of": "offshore",
        "co": "coastland",
        "other": "other",
    },
}

# NOSDRA's two-letter state codes. The nine Niger Delta states follow the
# NDDC Act definition.
STATES = [
    ("AB", "Abia", True), ("AK", "Akwa Ibom", True), ("BY", "Bayelsa", True),
    ("CR", "Cross River", True), ("DE", "Delta", True), ("ED", "Edo", True),
    ("IM", "Imo", True), ("ON", "Ondo", True), ("RI", "Rivers", True),
    ("AN", "Anambra", False), ("BA", "Bauchi", False), ("EK", "Ekiti", False),
    ("FC", "Federal Capital Territory", False), ("GO", "Gombe", False),
    ("KD", "Kaduna", False), ("KN", "Kano", False), ("KO", "Kogi", False),
    ("KT", "Katsina", False), ("KW", "Kwara", False), ("LA", "Lagos", False),
    ("NI", "Niger", False), ("OG", "Ogun", False), ("OS", "Osun", False),
    ("PL", "Plateau", False), ("SO", "Sokoto", False), ("ZA", "Zamfara", False),
]


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def upgrade() -> None:
    rows = ",".join(
        f"({_q(f)}, {_q(c)}, {_q(lbl)})" for f, codes in CODES.items() for c, lbl in codes.items()
    )
    op.execute(f"INSERT INTO ref.codes (field, code, label) VALUES {rows};")
    rows = ",".join(f"({_q(c)}, {_q(n)}, {d})" for c, n, d in STATES)
    op.execute(f"INSERT INTO ref.states (code, name, is_niger_delta) VALUES {rows};")


def downgrade() -> None:
    op.execute("TRUNCATE ref.codes, ref.states CASCADE;")
