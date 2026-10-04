"""Catalogue of every issue the validator can raise.

Severity decides what happens to the record:
  error   -> kept in clean.spills but excluded from analysis (analysable = false)
  warning -> analysed, but flagged wherever it is shown
  info    -> a correction we made, recorded so it can be audited

Codes are part of the API contract: add new ones, don't rename existing ones.
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
        IssueType("NOT_A_SPILL", _E, "Contaminant recorded as 'no spill'."),
        IssueType("STATUS_INVALID", _E, "NOSDRA marked the report invalid."),
        IssueType("OPERATOR_MISSING", _W, "No operating company recorded."),
        # Dates
        IssueType("DATE_MISSING", _E, "No incident date, so it can't be placed in time."),
        IssueType("DATE_UNPARSEABLE", _E, "Incident date isn't a valid date."),
        IssueType("DATE_IMPLAUSIBLE", _E, "Incident date is before the earliest plausible date."),
        IssueType("JIV_BEFORE_INCIDENT", _W, "Joint investigation dated before the incident."),
        # Quantity
        IssueType("QUANTITY_MISSING", _W, "No estimated quantity."),
        IssueType("QUANTITY_UNPARSEABLE", _W, "Estimated quantity isn't a number."),
        IssueType("QUANTITY_NEGATIVE", _W, "Negative quantity; treated as missing."),
        IssueType("QUANTITY_IMPLAUSIBLE", _W, "Quantity exceeds the largest plausible spill."),
        # Cause
        IssueType("CAUSE_MISSING", _W, "No cause recorded."),
        IssueType("CAUSE_UNKNOWN_CODE", _W, "Cause code not in the source legend."),
        # State
        IssueType("STATE_UNRECOGNISED", _W, "Reported state couldn't be matched to a state."),
        IssueType("STATE_MULTIPLE", _I, "Report lists more than one state; first one used."),
        # Coordinates (raised in Python)
        IssueType("COORD_MISSING", _E, "No coordinates."),
        IssueType("COORD_PARTIAL", _E, "Only one of latitude/longitude present."),
        IssueType("COORD_INVALID", _E, "Coordinates are NaN, zero, or not numbers."),
        # Coordinates (raised in PostGIS)
        IssueType("COORD_UNRESOLVED", _E,
                  "Coordinates aren't degrees and no correction placed them in Nigeria."),
        IssueType("COORD_OUTSIDE_NIGERIA", _E, "Point is outside Nigeria and its waters."),
        IssueType("COORD_REPROJECTED", _I, "Recovered from projected grid metres."),
        IssueType("COORD_DECIMAL_SHIFTED", _W, "Recovered by moving a misplaced decimal point."),
        IssueType("COORD_SWAPPED", _W, "Latitude and longitude were swapped."),
        IssueType("COORD_STATE_MISMATCH", _W, "Point falls in a different state from the one reported."),
        IssueType("COORD_LGA_MISMATCH", _W, "Point falls in a different LGA from the one reported."),
        IssueType("HABITAT_MISMATCH", _W, "Habitat (offshore/land) contradicts the point's location."),
        IssueType("COORD_REUSED", _W, "Same exact coordinate used by many separate incidents."),
        IssueType("LIKELY_DUPLICATE", _W, "Same operator, nearby place and date as another report."),
    ]
}


def make(code: str, message: str, field: str | None = None, **details: Any) -> Issue:
    return Issue(code, CATALOGUE[code].severity, message, field, details)
