"""GraphQL and GeoJSON endpoints, against the validated synthetic snapshot."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def client(validated: dict[str, dict[str, Any]]) -> Iterator[TestClient]:
    from sheen.analysis import exposure
    from sheen.api.app import app

    exposure.analyse()
    with TestClient(app) as c:
        yield c


def gql(client: TestClient, query: str, **variables: Any) -> dict[str, Any]:
    resp = client.post("/graphql", json={"query": query, "variables": variables})
    assert resp.status_code == 200
    body = resp.json()
    assert "errors" not in body, body["errors"]
    return body["data"]  # type: ignore[no-any-return]


def test_healthz_and_request_id(client: TestClient) -> None:
    resp = client.get("/healthz", headers={"x-request-id": "abc123"})
    assert resp.json() == {"status": "ok"}
    assert resp.headers["x-request-id"] == "abc123"


@pytest.mark.parametrize(
    ("spill_id", "location_step"),
    [
        ("1", "Reported coordinates used as-is"),
        ("2", "EPSG:26392"),
        ("3", "Not placed"),
        ("10", "packed degrees-minutes-seconds"),
    ],
)
def test_explain_covers_every_location_method(client: TestClient, spill_id: str, location_step: str) -> None:
    data = gql(
        client, "query($id: ID!) { explainSpill(id: $id) { steps { step outcome } rawRecord } }", id=spill_id
    )
    steps = {s["step"]: s["outcome"] for s in data["explainSpill"]["steps"]}
    assert location_step in steps["location"]
    assert data["explainSpill"]["rawRecord"]["id"] == spill_id


def test_filter_by_issue_and_paginate(client: TestClient) -> None:
    q = """query($after: String) {
      spills(filter: {analysable: true}, first: 2, after: $after) {
        totalCount hasNextPage endCursor items { id }
      }
    }"""
    first = gql(client, q)["spills"]
    second = gql(client, q, after=first["endCursor"])["spills"]
    ids = [i["id"] for i in first["items"] + second["items"]]
    assert len(ids) == len(set(ids)) == 4
    assert first["hasNextPage"]

    dupes = gql(client, '{ spills(filter: {issueCode: "LIKELY_DUPLICATE"}) { items { id } } }')
    assert [i["id"] for i in dupes["spills"]["items"]] == ["7"]


def test_nested_fields_resolve(client: TestClient) -> None:
    data = gql(
        client, '{ spill(id: "2") { lga { name stateName } issues { code } exposure { mangroveYear } } }'
    )
    s = data["spill"]
    assert s["lga"] == {"name": "Okrika", "stateName": "Rivers"}
    assert "COORD_REPROJECTED" in {i["code"] for i in s["issues"]}
    assert s["exposure"]["mangroveYear"] == 2020


def test_issue_types_include_counts(client: TestClient) -> None:
    types = {t["code"]: t["count"] for t in gql(client, "{ issueTypes { code count } }")["issueTypes"]}
    assert types["NOT_A_SPILL"] == 1
    assert types["COORD_DMS_PARSED"] == 1


def test_geojson_spills(client: TestClient) -> None:
    resp = client.get("/geojson/spills")
    assert resp.headers["content-type"].startswith("application/geo+json")
    fc = resp.json()
    assert fc["type"] == "FeatureCollection"
    assert all(f["geometry"]["type"] == "Point" for f in fc["features"])
    assert "8" not in {f["properties"]["id"] for f in fc["features"]}  # not a spill


def test_lga_summaries(client: TestClient) -> None:
    lgas = gql(client, '{ lgas(stateCode: "RI") { name spills mangroveHa2020 mangroveChangePct } }')["lgas"]
    by_name = {lga["name"]: lga for lga in lgas}
    # Analysable spills placed in Okrika: #1, #2, #7, #10 (#8 is "no spill").
    assert by_name["Okrika"]["spills"] == 4
    assert by_name["Okrika"]["mangroveChangePct"] is None  # no mangroves in the test geography


def test_operator_quality(client: TestClient) -> None:
    (op,) = gql(client, "{ operators(minReports: 1) { operator reports shareUnplaceable } }")["operators"]
    assert op["operator"] == "OPCO"
    assert 0 < op["shareUnplaceable"] < 1


def test_trends_by_lga_year(client: TestClient) -> None:
    body = client.get("/trends", params={"lga": "Okrika,Nowhere"}).json()
    assert body["unmatched_lgas"] == ["Nowhere"]
    assert body["total_spills"] == 4  # analysable spills placed in Okrika: 1, 2, 7, 10
    by_year = {p["period"]: p["spills"] for p in body["series"]}
    assert by_year["2018"] == 4
    assert by_year["2010"] == 0  # years without spills are still listed
    assert body["series"][-1]["partial"] is True


def test_trends_by_state_and_month(client: TestClient) -> None:
    body = client.get("/trends", params={"state": "by", "by": "month"}).json()
    months = {p["period"]: p["spills"] for p in body["series"] if p["spills"]}
    assert months == {"2018-04": 1}  # spill 4 is reported as Rivers but lies in Bayelsa
