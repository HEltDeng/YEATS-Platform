"""Teacher submission policy and private knowledge-change receipts."""
from alembic import op
import sqlalchemy as sa
revision='20261003_teacher_workflows'
down_revision='20261003_grading_deadline'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('homework',sa.Column('submission_requirement',sa.String(24),nullable=False,server_default='image_or_text'))
    op.add_column('homework',sa.Column('submission_instructions',sa.Text(),nullable=False,server_default=''))
    op.create_table('knowledge_change_requests',sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('teacher_id',sa.String(36),sa.ForeignKey('accounts.id'),nullable=False),sa.Column('category_id',sa.String(36),sa.ForeignKey('categories.id')),sa.Column('knowledge_id',sa.String(36),sa.ForeignKey('knowledge.id')),sa.Column('change_type',sa.String(20),nullable=False),sa.Column('title',sa.String(200),nullable=False),sa.Column('text',sa.Text(),nullable=False),sa.Column('attachment_ids',sa.JSON(),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('response',sa.Text(),nullable=False),sa.Column('processed_by',sa.String(36),sa.ForeignKey('accounts.id')),sa.Column('processed_at',sa.DateTime()))
    connection=op.get_bind()
    previous=connection.execute(sa.text("SELECT id, created_at, actor_id, detail FROM audit WHERE action='knowledge_change_request'"))
    table=sa.table('knowledge_change_requests',sa.column('id'),sa.column('created_at'),sa.column('teacher_id'),sa.column('category_id'),sa.column('knowledge_id'),sa.column('change_type'),sa.column('title'),sa.column('text'),sa.column('attachment_ids',sa.JSON()),sa.column('status'),sa.column('response'))
    for row in previous:
        detail=row.detail
        if isinstance(detail,str):
            import json
            detail=json.loads(detail)
        if row.actor_id and detail.get('text'):
            connection.execute(table.insert().values(id=row.id,created_at=row.created_at,teacher_id=row.actor_id,category_id=None,knowledge_id=None,change_type='correction',title='迁移的历史内容变更申请',text=detail['text'],attachment_ids=[],status='pending',response=''))
def downgrade():
    op.drop_table('knowledge_change_requests')
    op.drop_column('homework','submission_instructions')
    op.drop_column('homework','submission_requirement')
