"""Add company field to BackupStatus

Revision ID: 07473fd60fb1
Revises: 09453558e4a0
Create Date: 2025-05-21 13:37:59.932306

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '07473fd60fb1'
down_revision = '09453558e4a0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('backup_status', schema=None) as batch_op:
        batch_op.add_column(sa.Column('company', sa.String(length=100), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('backup_status', schema=None) as batch_op:
        batch_op.drop_column('company')

    # ### end Alembic commands ###
