"""add wards and ward level reports

Revision ID: b4e2f19a3c10
Revises: 868a9446aa68
Create Date: 2026-11-10 17:15:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4e2f19a3c10'
down_revision: Union[str, Sequence[str], None] = '868a9446aa68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ZONE_CODE_BACKFILL = {
    'Bommanahalli': 'BMH',
    'CV Raman Nagar': 'CVRN',
    'Hebbal': 'HEB',
    'Pulakeshi Nagar': 'PN',
    'Sarvagna Nagar': 'SN',
    'Shanthi Nagar': 'SNTR',
    'Sivaji Nagar': 'SVJR',
}


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add zone_code to zones and backfill initial zone codes
    op.add_column('zones', sa.Column('zone_code', sa.String(length=32), nullable=True))
    for zname, zcode in ZONE_CODE_BACKFILL.items():
        bind.execute(
            sa.text('UPDATE zones SET zone_code = :zcode WHERE zone_name = :zname AND zone_code IS NULL'),
            {'zcode': zcode, 'zname': zname},
        )

    # 2. Create wards table
    op.create_table(
        'wards',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('zone_id', sa.Integer(), nullable=False),
        sa.Column('ward_name', sa.String(length=200), nullable=False),
        sa.Column('ward_number', sa.String(length=64), nullable=False),
        sa.Column('ward_code', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['zone_id'], ['zones.id'], name=op.f('fk_wards_zone_id_zones'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_wards')),
        sa.UniqueConstraint('zone_id', 'ward_code', name='uq_wards_zone_ward_code'),
        sa.UniqueConstraint('zone_id', 'ward_number', name='uq_wards_zone_ward_number'),
    )
    op.create_index('ix_wards_zone_id', 'wards', ['zone_id'], unique=False)

    # 3. Add nullable ward_id columns first so any legacy data can be backfilled safely
    op.add_column('report_files', sa.Column('ward_id', sa.Integer(), nullable=True))
    op.add_column('report_file_versions', sa.Column('ward_id', sa.Integer(), nullable=True))
    op.add_column('merged_reports', sa.Column('ward_id', sa.Integer(), nullable=True))
    op.add_column('processing_logs', sa.Column('ward_id', sa.Integer(), nullable=True))

    legacy_zone_rows = bind.execute(
        sa.text(
            '''
            SELECT DISTINCT zone_id FROM (
                SELECT zone_id FROM report_files
                UNION
                SELECT zone_id FROM merged_reports
                UNION
                SELECT zone_id FROM processing_logs
            ) AS legacy_zones
            '''
        )
    ).fetchall()
    now = datetime.now(timezone.utc)
    for (legacy_zone_id,) in legacy_zone_rows:
        ward_id = bind.execute(
            sa.text('SELECT id FROM wards WHERE zone_id = :zid ORDER BY id ASC LIMIT 1'),
            {'zid': legacy_zone_id},
        ).scalar()
        if ward_id is None:
            ward_id = bind.execute(
                sa.text(
                    '''
                    INSERT INTO wards (zone_id, ward_name, ward_number, ward_code, status, created_at, updated_at)
                    VALUES (:zid, 'Default Ward', 'LEGACY', :wcode, 'active', :now, :now)
                    RETURNING id
                    '''
                ),
                {'zid': legacy_zone_id, 'wcode': f'Z{legacy_zone_id}-LEGACY', 'now': now},
            ).scalar()
        bind.execute(
            sa.text('UPDATE report_files SET ward_id = :wid WHERE zone_id = :zid AND ward_id IS NULL'),
            {'wid': ward_id, 'zid': legacy_zone_id},
        )
        bind.execute(
            sa.text('UPDATE merged_reports SET ward_id = :wid WHERE zone_id = :zid AND ward_id IS NULL'),
            {'wid': ward_id, 'zid': legacy_zone_id},
        )
        bind.execute(
            sa.text('UPDATE processing_logs SET ward_id = :wid WHERE zone_id = :zid AND ward_id IS NULL'),
            {'wid': ward_id, 'zid': legacy_zone_id},
        )

    bind.execute(
        sa.text(
            '''
            UPDATE report_file_versions rfv
            SET ward_id = rf.ward_id
            FROM report_files rf
            WHERE rfv.report_file_id = rf.id AND rfv.ward_id IS NULL
            '''
        )
    )

    # 4. Enforce NOT NULL, foreign keys, constraints, and indexes at ward granularity
    op.alter_column('report_files', 'ward_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('report_file_versions', 'ward_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('merged_reports', 'ward_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('processing_logs', 'ward_id', existing_type=sa.Integer(), nullable=False)

    op.create_foreign_key(
        op.f('fk_report_files_ward_id_wards'), 'report_files', 'wards', ['ward_id'], ['id'], ondelete='RESTRICT'
    )
    op.create_foreign_key(
        op.f('fk_report_file_versions_ward_id_wards'),
        'report_file_versions',
        'wards',
        ['ward_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        op.f('fk_merged_reports_ward_id_wards'), 'merged_reports', 'wards', ['ward_id'], ['id'], ondelete='RESTRICT'
    )
    op.create_foreign_key(
        op.f('fk_processing_logs_ward_id_wards'), 'processing_logs', 'wards', ['ward_id'], ['id'], ondelete='RESTRICT'
    )

    op.drop_index(
        'uq_active_report_file_slot',
        table_name='report_files',
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        'uq_active_report_file_slot',
        'report_files',
        ['customer_id', 'region_id', 'zone_id', 'ward_id', 'report_type'],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index('ix_report_files_ward_type', 'report_files', ['ward_id', 'report_type'], unique=False)
    op.create_index('ix_rfv_ward_id', 'report_file_versions', ['ward_id'], unique=False)

    op.drop_constraint('uq_merged_report_zone_slot', 'merged_reports', type_='unique')
    op.create_unique_constraint(
        'uq_merged_report_ward_slot', 'merged_reports', ['customer_id', 'region_id', 'zone_id', 'ward_id']
    )
    op.create_index('ix_merged_reports_ward_id', 'merged_reports', ['ward_id'], unique=False)
    op.create_index('ix_processing_logs_ward_created', 'processing_logs', ['ward_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_processing_logs_ward_created', table_name='processing_logs')
    op.drop_index('ix_merged_reports_ward_id', table_name='merged_reports')
    op.drop_constraint('uq_merged_report_ward_slot', 'merged_reports', type_='unique')
    op.create_unique_constraint('uq_merged_report_zone_slot', 'merged_reports', ['customer_id', 'region_id', 'zone_id'])

    op.drop_index('ix_rfv_ward_id', table_name='report_file_versions')
    op.drop_index('ix_report_files_ward_type', table_name='report_files')
    op.drop_index(
        'uq_active_report_file_slot',
        table_name='report_files',
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        'uq_active_report_file_slot',
        'report_files',
        ['customer_id', 'region_id', 'zone_id', 'report_type'],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.drop_constraint(op.f('fk_processing_logs_ward_id_wards'), 'processing_logs', type_='foreignkey')
    op.drop_constraint(op.f('fk_merged_reports_ward_id_wards'), 'merged_reports', type_='foreignkey')
    op.drop_constraint(op.f('fk_report_file_versions_ward_id_wards'), 'report_file_versions', type_='foreignkey')
    op.drop_constraint(op.f('fk_report_files_ward_id_wards'), 'report_files', type_='foreignkey')

    op.drop_column('processing_logs', 'ward_id')
    op.drop_column('merged_reports', 'ward_id')
    op.drop_column('report_file_versions', 'ward_id')
    op.drop_column('report_files', 'ward_id')

    op.drop_index('ix_wards_zone_id', table_name='wards')
    op.drop_table('wards')
    op.drop_column('zones', 'zone_code')

