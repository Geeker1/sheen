"""Every problem the checks can find.

The severity decides what happens to the report:
  error    kept, but left out of the analysis
  warning  used, but flagged
  info     a fix that was made, kept as a record

Other code relies on these codes, so add new ones but don't rename old ones.
"""

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class IssueType:
    code: str
    severity: Severity
    description: str


@dataclass
class Issue:
    code: str
    severity: Severity
    message: str
    field: str | None = None
    details: dict[str, Any] = dataclass_field(default_factory=dict)


_E, _W, _I = Severity.ERROR, Severity.WARNING, Severity.INFO

CATALOGUE: dict[str, IssueType] = {
    t.code: t
    for t in [
        # Record-level
        IssueType("NOT_A_SPILL", _E, "The report says there was no spill."),
        IssueType("STATUS_INVALID", _E, "NOSDRA marked the report invalid."),
        IssueType("OPERATOR_MISSING", _W, "No operating company recorded."),
        # Dates
        IssueType("DATE_MISSING", _E, "No spill date."),
        IssueType("DATE_UNPARSEABLE", _E, "The spill date isn't a real date."),
        IssueType("DATE_IMPLAUSIBLE", _E, "The spill date is too early to be real, or in the future."),
        IssueType("JIV_BEFORE_INCIDENT", _W, "Site visit dated before the spill."),
        # Quantity
        IssueType("QUANTITY_MISSING", _W, "No estimated quantity."),
        IssueType("QUANTITY_UNPARSEABLE", _W, "Estimated quantity isn't a number."),
        IssueType("QUANTITY_NEGATIVE", _W, "Negative quantity; treated as missing."),
        IssueType("QUANTITY_IMPLAUSIBLE", _W, "Bigger than any believable spill."),
        # Cause
        IssueType("CAUSE_MISSING", _W, "No cause recorded."),
        IssueType("CAUSE_UNKNOWN_CODE", _W, "A cause code NOSDRA doesn't define."),
        # State
        IssueType("STATE_UNRECOGNISED", _W, "The state name couldn't be recognised."),
        IssueType("STATE_MULTIPLE", _I, "Report lists more than one state; first one used."),
        # Coordinates (raised in Python)
        IssueType("COORD_MISSING", _E, "No coordinates."),
        IssueType("COORD_PARTIAL", _E, "Only one of latitude/longitude present."),
        IssueType("COORD_INVALID", _E, "Coordinates are zero or not numbers."),
        # Coordinates (raised in PostGIS)
        IssueType("COORD_UNRESOLVED", _E, "None of the possible fixes lands where the report says."),
        IssueType("COORD_OUTSIDE_NIGERIA", _E, "Point is outside Nigeria and its waters."),
        IssueType("COORD_REPROJECTED", _I, "Converted from Nigerian grid coordinates."),
        IssueType("COORD_DECIMAL_SHIFTED", _W, "Fixed by moving a decimal point."),
        IssueType("COORD_SWAPPED", _W, "Latitude and longitude were swapped."),
        IssueType("COORD_DMS_PARSED", _I, "Read as degrees-minutes-seconds written with no spaces."),
        IssueType("COORD_STATE_MISMATCH", _W, "Point falls in a different state from the one reported."),
        IssueType("COORD_LGA_MISMATCH", _W, "Point falls in a different LGA from the one reported."),
        IssueType("HABITAT_MISMATCH", _W, "Report says land or offshore, but the point is the other."),
        IssueType("COORD_REUSED", _W, "Many reports share exactly this point."),
        IssueType("LIKELY_DUPLICATE", _W, "Same company, place and date as an earlier report."),
    ]
}


def make(code: str, message: str, field: str | None = None, **details: Any) -> Issue:
    return Issue(code, CATALOGUE[code].severity, message, field, details)
