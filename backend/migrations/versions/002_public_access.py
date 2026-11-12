"""Explicit publication and indexes for public read models."""
from alembic import op
import sqlalchemy as sa
revision='002'
down_revision='001'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('connections',sa.Column('publish_enabled',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_index('ix_posts_connection_published','posts',['connection_id','published_at','id'])
    op.create_index('ix_observations_latest','post_observations',['post_id','captured_at','id'])
    op.create_index('ix_account_observations_latest','account_observations',['connection_id','captured_at','id'])

def downgrade():
    op.drop_index('ix_account_observations_latest',table_name='account_observations')
    op.drop_index('ix_observations_latest',table_name='post_observations')
    op.drop_index('ix_posts_connection_published',table_name='posts')
    op.drop_column('connections','publish_enabled')
