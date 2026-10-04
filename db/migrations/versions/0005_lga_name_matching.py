"""LGA name matching function

Plain trigram similarity on LGA names fails both ways: 'Ukwa West' scores
0.33 against 'Saki West' (shared word) and 'Ahoada West' 0.50 against
'Ahoada East', while a real typo like 'Deyema' vs 'Degema' scores 0.40.

ref.lga_name_similarity compares the core name with compass words and
'LGA' removed, and returns 0 when the two names carry different compass
words, so twin LGAs (Ukwa East/West) never match each other.

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
