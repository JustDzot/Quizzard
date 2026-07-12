"""add_multiplayer_and_xp

Revision ID: a7cd7ab22c49
Revises: 995c9a2eb819
Create Date: 2026-07-12 10:19:56.532092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7cd7ab22c49'
down_revision: Union[str, Sequence[str], None] = '995c9a2eb819'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to users table
    op.add_column('users', sa.Column('xp', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('wins', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('losses', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('draws', sa.Integer(), server_default='0', nullable=False))

    # Create matchmaking_queue table
    op.create_table(
        'matchmaking_queue',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )

    # Create multiplayer_games table
    op.create_table(
        'multiplayer_games',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('player1_id', sa.Integer(), nullable=False),
        sa.Column('player2_id', sa.Integer(), nullable=False),
        sa.Column('category_options', sa.JSON(), nullable=True),
        sa.Column('player1_vote', sa.String(length=255), nullable=True),
        sa.Column('player2_vote', sa.String(length=255), nullable=True),
        sa.Column('chosen_category', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='voting', nullable=False),
        sa.Column('player1_score', sa.Integer(), server_default='0', nullable=False),
        sa.Column('player2_score', sa.Integer(), server_default='0', nullable=False),
        sa.Column('player1_finished', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('player2_finished', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('player1_answers', sa.JSON(), nullable=True),
        sa.Column('player2_answers', sa.JSON(), nullable=True),
        sa.Column('player1_start_time', sa.DateTime(), nullable=True),
        sa.Column('player1_end_time', sa.DateTime(), nullable=True),
        sa.Column('player2_start_time', sa.DateTime(), nullable=True),
        sa.Column('player2_end_time', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['player1_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player2_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create multiplayer_questions table
    op.create_table(
        'multiplayer_questions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('options', sa.JSON(), nullable=False),
        sa.Column('correct_option_index', sa.Integer(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['multiplayer_games.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('multiplayer_questions')
    op.drop_table('multiplayer_games')
    op.drop_table('matchmaking_queue')
    op.drop_column('users', 'draws')
    op.drop_column('users', 'losses')
    op.drop_column('users', 'wins')
    op.drop_column('users', 'xp')
