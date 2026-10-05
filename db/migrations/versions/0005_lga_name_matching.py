"""LGA name matching function

A standard text similarity score rated 'Ukwa West' and 'Saki West' (0.33),
or 'Ahoada West' and 'Ahoada East' (0.50), as more alike than the real typo
'Deyema' and 'Degema' (0.40).

This function ignores words like North, West and 'LGA', and treats names
with different directions, like Ukwa East and Ukwa West, as different places.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
    CREATE FUNCTION ref.lga_key(name text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
        SELECT trim(regexp_replace(
                   regexp_replace(lower(name), '[-/_.,]+', ' ', 'g'),
                   '\m(north|south|east|west|central|lga|local|government|area)\M|\s+', ' ', 'g'))
    $$;

    CREATE FUNCTION ref.lga_directions(name text) RETURNS text[]
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
        SELECT coalesce(array_agg(DISTINCT m[1]), '{}')
        FROM regexp_matches(lower(name), '\m(north|south|east|west|central)\M', 'g') AS m
    $$;

    CREATE FUNCTION ref.lga_name_similarity(a text, b text) RETURNS real
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
        SELECT CASE
            WHEN cardinality(ref.lga_directions(a)) > 0
             AND cardinality(ref.lga_directions(b)) > 0
             AND NOT ref.lga_directions(a) && ref.lga_directions(b) THEN 0
            ELSE similarity(ref.lga_key(a), ref.lga_key(b))
        END
    $$;
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION ref.lga_name_similarity(text, text);
    DROP FUNCTION ref.lga_directions(text);
    DROP FUNCTION ref.lga_key(text);
    """)
