"""Persist email verification, preferences and transactional delivery records."""
from alembic import op
import sqlalchemy as sa

revision = '0007_notification_delivery'
down_revision = '0006_requirement_workflow'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sys_mail_preference',
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('sys_user.id'), primary_key=True),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('mode', sa.String(16), nullable=False, server_default='TASKS'),
        sa.Column('verified_at', sa.DateTime(timezone=True)),
        sa.Column('verified_email', sa.String(254)), sa.Column('pending_email', sa.String(254)),
        sa.Column('challenge_id', sa.String(36)), sa.Column('challenge_expires_at', sa.DateTime(timezone=True)),
        sa.Column('challenge_user_revision', sa.Integer()),
        sa.Column('challenge_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('requested_at', sa.DateTime(timezone=True)))
    op.create_table('sys_notification_delivery',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_id', sa.String(36), sa.ForeignKey('sys_collaboration_event.id'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('sys_user.id'), nullable=False),
        sa.Column('channel', sa.String(16), nullable=False), sa.Column('status', sa.String(16), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False), sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_error', sa.String(64)), sa.Column('queued_email', sa.String(254)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('event_id', 'user_id', 'channel', name='uq_delivery_event_user_channel'))
    op.create_index('ix_sys_notification_delivery_next_attempt_at', 'sys_notification_delivery', ['next_attempt_at'])
    op.execute('INSERT INTO sys_mail_preference (user_id) SELECT id FROM sys_user')
    op.create_index('uq_requirement_single_actor_role', 'rd_requirement_participant', ['requirement_id', 'role'], unique=True, postgresql_where=sa.text("active AND role IN ('CONFIRM', 'ACCEPT')"))
    # Enabling the worker must not replay old collaboration history.
    op.execute('UPDATE sys_collaboration_event SET processed_at=CURRENT_TIMESTAMP WHERE processed_at IS NULL')


def downgrade():
    raise RuntimeError('Mail delivery history requires a reviewed recovery; automatic downgrade is disabled')
