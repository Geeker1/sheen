"""The location checks, run in order during validation.

Each step is one SQL statement, so its time and row count can be logged. The
`cands` table holds every possible reading of each report's coordinates.
Distances are in metres using UTM zone 32N, which is accurate enough across
the whole Delta.
"""

# Which reading to prefer when everything else is equal.
METHOD_PRIORITY = {"reported": 0, "swapped": 1, "dms": 2, "reprojected": 3, "decimal_shift": 4}

STEPS: list[tuple[str, str]] = [
    (
        "nigeria_outline",
        """
            CREATE TEMP TABLE nga ON COMMIT DROP AS
            SELECT ST_Union(geom) AS geom, ST_Union(geom_utm) AS geom_utm
            FROM ref.admin_areas WHERE level = 1
        """,
    ),
    (
        # Nigeria's border, cut into small pieces so distance checks are fast.
        "nigeria_edge",
        """
            CREATE TEMP TABLE nga_edge ON COMMIT DROP AS
            SELECT ST_Subdivide(ST_Boundary(geom_utm), 64) AS geom_utm FROM nga
        """,
    ),
    ("nigeria_edge_index", "CREATE INDEX ON nga_edge USING gist (geom_utm)"),
    (
        # One row per possible reading, with plain true/false facts about where it
        # lands. None of these can be empty: Postgres sorts empty values first,
        # which once pushed a wrong reading to the top.
        "check_readings",
        """
            CREATE TEMP TABLE readings ON COMMIT DROP AS
            SELECT c.spill_id, c.method, c.priority, c.srid, c.geom,
                   s.state_code IS NOT NULL AS state_given,
                   s.lga_reported IS NOT NULL AS lga_given,
                   state.pcode IS NOT NULL AS on_land,
                   coalesce(state.state_code = s.state_code, false) AS in_reported_state,
                   state.pcode IS NULL
                       AND ST_Y(c.geom) <= %(offshore_max_lat)s
                       AND ST_X(c.geom) BETWEEN %(offshore_min_lon)s AND %(offshore_max_lon)s
                       AND ST_DWithin(ST_Transform(c.geom, 32632), nga.geom_utm, %(offshore_max_m)s)
                       AS at_sea,
                   -- Each grid is meant for one part of the country.
                   coalesce(ST_X(c.geom) >= zone.min_lon AND ST_X(c.geom) < zone.max_lon, true)
                       AS in_own_zone,
                   -- Near an area with the name the report gives? Only worked out for
                   -- fixes, and within a few km because the grid zones disagree by that much.
                   c.method <> 'reported' AND s.lga_reported IS NOT NULL AND EXISTS (
                       SELECT 1 FROM ref.admin_areas area
                       WHERE area.level = 2
                         AND ref.lga_name_similarity(s.lga_reported, area.name) >= %(lga_min_similarity)s
                         AND ST_DWithin(area.geom_utm, ST_Transform(c.geom, 32632), %(lga_tie_break_m)s)
                   ) AS near_reported_lga
            FROM cands c
            JOIN clean.spills s USING (spill_id)
            CROSS JOIN nga
            LEFT JOIN ref.admin_areas state
                   ON state.level = 1 AND ST_Intersects(state.geom, c.geom)
            LEFT JOIN (VALUES (26391, -180, 6.5), (26392, 6.5, 10.5), (26393, 10.5, 180),
                              (32631, -180, 6.0), (32632, 6.0, 12.0)) AS zone (srid, min_lon, max_lon)
                   ON zone.srid = c.srid
        """,
    ),
    (
        # For each report, keep the best reading that's allowed.
        "choose_location",
        """
            UPDATE clean.spills s
            SET geom = best.geom, geom_method = best.method
            FROM (
                SELECT DISTINCT ON (spill_id) spill_id, geom, method
                FROM readings
                WHERE (on_land OR at_sea)
                  AND (method = 'reported'                          -- as published
                       OR in_reported_state                         -- a fix in the state it names
                       OR (NOT state_given AND near_reported_lga)   -- no state: near the area it names
                       OR (NOT state_given AND NOT lga_given))      -- the report names neither
                ORDER BY spill_id,
                         method = 'reported' DESC,  -- the published location if it makes sense
                         in_reported_state DESC,    -- a state beats an area name; names repeat
                         near_reported_lga DESC,
                         in_own_zone DESC,
                         on_land DESC,
                         priority
            ) best
            WHERE best.spill_id = s.spill_id
        """,
    ),
    (
        "issue_unplaceable",
        """
            INSERT INTO clean.spill_issues (spill_id, code, severity, field, message, details)
            SELECT spill_id,
                   CASE WHEN tried_fix THEN 'COORD_UNRESOLVED' ELSE 'COORD_OUTSIDE_NIGERIA' END,
                   'error', 'latitude/longitude',
                   CASE WHEN tried_fix
                        THEN format('None of the %%s possible fixes lands where the report says', n)
                        ELSE format('Point at %%s, %%s is outside Nigeria and its waters',
                                    round(ST_Y(p)::numeric, 4), round(ST_X(p)::numeric, 4)) END,
                   jsonb_build_object('candidates_tried', n)
            FROM (
                SELECT s.spill_id,
                       bool_or(c.method IN ('reprojected', 'decimal_shift', 'dms')) AS tried_fix,
                       (array_agg(c.geom ORDER BY c.priority))[1] AS p,
                       count(*) AS n
                FROM clean.spills s JOIN cands c USING (spill_id)
                WHERE s.geom IS NULL
                GROUP BY s.spill_id
            ) x;
        """,
    ),
    (
        "issue_corrections",
        """
            INSERT INTO clean.spill_issues (spill_id, code, severity, field, message, details)
            SELECT s.spill_id,
                   CASE s.geom_method WHEN 'reprojected' THEN 'COORD_REPROJECTED'
                                      WHEN 'decimal_shift' THEN 'COORD_DECIMAL_SHIFTED'
                                      WHEN 'dms' THEN 'COORD_DMS_PARSED'
                                      ELSE 'COORD_SWAPPED' END,
                   CASE WHEN s.geom_method IN ('reprojected', 'dms') THEN 'info' ELSE 'warning' END,
                   'latitude/longitude',
                   format('Reported %%s, %%s; corrected to %%s, %%s (%%s)',
                          r.payload->>'latitude', r.payload->>'longitude',
                          round(ST_Y(s.geom)::numeric, 6), round(ST_X(s.geom)::numeric, 6),
                          CASE s.geom_method WHEN 'reprojected' THEN 'EPSG:' || c.srid
                               WHEN 'dms' THEN 'packed degrees-minutes-seconds'
                               ELSE replace(s.geom_method, '_', ' ') END),
                   jsonb_build_object('srid', c.srid,
                                      'reported_lat', r.payload->>'latitude',
                                      'reported_lon', r.payload->>'longitude')
            FROM clean.spills s
            JOIN raw.spill_reports r ON r.run_id = s.raw_run_id AND r.source_id = s.spill_id
            JOIN cands c ON c.spill_id = s.spill_id AND c.method = s.geom_method
                        AND ST_Equals(c.geom, s.geom)
            WHERE s.geom_method IN ('reprojected', 'decimal_shift', 'swapped', 'dms');
        """,
    ),
    (
        "assign_lga",
        """
            -- The area the point is in, or the nearest within 5 km (the coastline isn't exact).
            UPDATE clean.spills s
            SET lga_pcode = (
                SELECT a.pcode FROM ref.admin_areas a
                WHERE a.level = 2 AND ST_DWithin(a.geom_utm, s.geom_utm, 5000)
                ORDER BY a.geom_utm <-> s.geom_utm
                LIMIT 1)
            WHERE s.geom IS NOT NULL;
        """,
    ),
    (
        "issue_state_mismatch",
        """
            INSERT INTO clean.spill_issues (spill_id, code, severity, field, message, details)
            SELECT s.spill_id, 'COORD_STATE_MISMATCH', 'warning', 'statesaffected',
                   format('Reported in %%s but the point is in %%s (%%s LGA)',
                          rs.name, landed.name, lga.name),
                   jsonb_build_object('reported_state', s.state_code,
                                      'located_state_pcode', landed.pcode,
                                      'located_lga_pcode', lga.pcode)
            FROM clean.spills s
            JOIN ref.states rs ON rs.code = s.state_code
            JOIN ref.admin_areas lga ON lga.pcode = s.lga_pcode
            JOIN ref.admin_areas landed ON landed.pcode = lga.parent_pcode
            JOIN ref.admin_areas reported ON reported.level = 1 AND reported.state_code = s.state_code
            WHERE landed.state_code IS DISTINCT FROM s.state_code
              AND NOT ST_DWithin(reported.geom_utm, s.geom_utm, %(state_tolerance_m)s);
        """,
    ),
    (
        "issue_lga_mismatch",
        """
            -- Flag unless the name matches the LGA the point is in, or one within 2 km.
            INSERT INTO clean.spill_issues (spill_id, code, severity, field, message, details)
            SELECT s.spill_id, 'COORD_LGA_MISMATCH', 'warning', 'lga',
                   format('Reported LGA %%L; point is in %%s', s.lga_reported, lga.name),
                   jsonb_build_object('reported', s.lga_reported, 'located', lga.name,
                                      'similarity',
                                      round(ref.lga_name_similarity(s.lga_reported, lga.name)::numeric, 2))
            FROM clean.spills s
            JOIN ref.admin_areas lga ON lga.pcode = s.lga_pcode
            WHERE s.lga_reported IS NOT NULL
              AND ref.lga_name_similarity(s.lga_reported, lga.name) < %(lga_min_similarity)s
              AND NOT EXISTS (
                  SELECT 1 FROM ref.admin_areas near
                  WHERE near.level = 2
                    AND ST_DWithin(near.geom_utm, s.geom_utm, 2000)
                    AND ref.lga_name_similarity(s.lga_reported, near.name) >= %(lga_min_similarity)s);
        """,
    ),
    (
        "issue_habitat_mismatch",
        """
            INSERT INTO clean.spill_issues (spill_id, code, severity, field, message, details)
            SELECT s.spill_id, 'HABITAT_MISMATCH', 'warning', 'spillareahabitat',
                   CASE WHEN s.habitat_codes = '{of}'
                        THEN 'Habitat is offshore but the point is inland'
                        ELSE 'Habitat is land but the point is offshore' END,
                   jsonb_build_object('habitat', s.habitat_codes)
            FROM clean.spills s CROSS JOIN nga
            WHERE s.geom IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM nga_edge e
                              WHERE ST_DWithin(e.geom_utm, s.geom_utm, 2000))
              AND (   (s.habitat_codes = '{of}' AND ST_Intersects(nga.geom, s.geom))
                   OR (s.habitat_codes = '{la}' AND NOT ST_Intersects(nga.geom, s.geom)));
        """,
    ),
    (
        "issue_reused_coordinates",
        """
            INSERT INTO clean.spill_issues (spill_id, code, severity, field, message, details)
            SELECT s.spill_id, 'COORD_REUSED', 'warning', 'latitude/longitude',
                   format('Same coordinate used by %%s separate reports', g.n),
                   jsonb_build_object('reports_at_point', g.n)
            FROM clean.spills s
            JOIN (SELECT geom, count(*) AS n FROM clean.spills
                  WHERE geom IS NOT NULL GROUP BY geom
                  HAVING count(*) >= %(reused_min)s) g
              ON ST_Equals(g.geom, s.geom);
        """,
    ),
    (
        "issue_duplicates",
        """
            -- Flag the later report of each pair, pointing back to the earlier one.
            WITH eligible AS (
                SELECT * FROM clean.spills s
                WHERE s.geom IS NOT NULL AND s.incident_date IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM clean.spill_issues i
                                  WHERE i.spill_id = s.spill_id
                                    AND i.code IN ('NOT_A_SPILL', 'STATUS_INVALID'))
            )
            INSERT INTO clean.spill_issues (spill_id, code, severity, field, message, details)
            SELECT b.spill_id, 'LIKELY_DUPLICATE', 'warning', NULL,
                   format('Same operator, %%s m and %%s day(s) from report %%s',
                          round(ST_Distance(a.geom_utm, b.geom_utm)),
                          abs(b.incident_date - a.incident_date), a.spill_id),
                   jsonb_build_object('duplicate_of', a.spill_id,
                                      'distance_m', round(ST_Distance(a.geom_utm, b.geom_utm)),
                                      'same_incident_number',
                                      coalesce(a.incident_number = b.incident_number, false))
            FROM eligible a
            JOIN eligible b
              ON a.operator = b.operator
             AND a.spill_id::bigint < b.spill_id::bigint
             AND abs(b.incident_date - a.incident_date) <= %(dup_window_days)s
             AND ST_DWithin(a.geom_utm, b.geom_utm, %(dup_radius_m)s);
        """,
    ),
    (
        "set_analysable",
        """
            UPDATE clean.spills s
            SET analysable = s.geom IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM clean.spill_issues i
                WHERE i.spill_id = s.spill_id AND i.severity = 'error');
        """,
    ),
]
