"""Create the historical occupation sectors table and spatial index."""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "occupation_sectors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("geometry", Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.UniqueConstraint("code", name="uq_occupation_sectors_code"),
        sa.CheckConstraint("code IN ('soviet', 'american', 'british', 'french')", name="ck_sector_code"),
        sa.CheckConstraint("NOT ST_IsEmpty(geometry) AND ST_IsValid(geometry)", name="ck_sector_geometry"),
        sa.CheckConstraint("length(trim(source_name)) > 0 AND length(trim(source_url)) > 0", name="ck_sector_source"),
    )
    op.create_index("idx_occupation_sectors_geometry", "occupation_sectors", ["geometry"], postgresql_using="gist")


def downgrade():
    op.drop_index("idx_occupation_sectors_geometry", table_name="occupation_sectors")
    op.drop_table("occupation_sectors")
    # PostGIS may be shared with other tables, so leave the extension installed.
