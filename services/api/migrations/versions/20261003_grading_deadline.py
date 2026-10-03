"""Separate the optional grading deadline from the student submission deadline."""
from alembic import op
import sqlalchemy as sa
revision='20261003_grading_deadline'
down_revision='fed048e339a9'
branch_labels=None
depends_on=None
def upgrade():op.add_column('homework',sa.Column('grading_due_at',sa.DateTime(),nullable=True))
def downgrade():op.drop_column('homework','grading_due_at')
