"""Reconcile models with DB: rename friend_request indexes, drop redundant PK indexes.

Revision ID: 224dc8e7975c
Revises: n4o5p6q7r8s9
Create Date: 2026-03-22 18:11:16.287233+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '224dc8e7975c'
down_revision: Union[str, None] = 'n4o5p6q7r8s9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # friend_requests: replace old indexes with per-column indexes matching model
    op.drop_index(op.f('ix_friend_requests_from_user'), table_name='friend_requests')
    op.drop_index(op.f('ix_friend_requests_to_user_status'), table_name='friend_requests')
    op.drop_constraint(op.f('uq_friend_requests_users'), 'friend_requests', type_='unique')
    op.create_index(op.f('ix_friend_requests_from_user_id'), 'friend_requests', ['from_user_id'], unique=False)
    op.create_index(op.f('ix_friend_requests_to_user_id'), 'friend_requests', ['to_user_id'], unique=False)

    # Drop redundant single-column indexes on composite PK columns
    # (the composite PK already provides lookup by the first column)
    op.drop_index(op.f('ix_friendships_user'), table_name='friendships')
    op.drop_index(op.f('ix_recipe_book_users_user_id'), table_name='recipe_book_users')
    op.drop_index(op.f('ix_recipe_ingredients_ingredient_id'), table_name='recipe_ingredients')
    op.drop_index(op.f('ix_user_favorites_user_id'), table_name='user_favorites')


def downgrade() -> None:
    # Recreate redundant PK indexes
    op.create_index(op.f('ix_user_favorites_user_id'), 'user_favorites', ['user_id'], unique=False)
    op.create_index(op.f('ix_recipe_ingredients_ingredient_id'), 'recipe_ingredients', ['ingredient_id'], unique=False)
    op.create_index(op.f('ix_recipe_book_users_user_id'), 'recipe_book_users', ['user_id'], unique=False)
    op.create_index(op.f('ix_friendships_user'), 'friendships', ['user_id'], unique=False)

    # Restore old friend_requests indexes
    op.drop_index(op.f('ix_friend_requests_to_user_id'), table_name='friend_requests')
    op.drop_index(op.f('ix_friend_requests_from_user_id'), table_name='friend_requests')
    op.create_unique_constraint(op.f('uq_friend_requests_users'), 'friend_requests', ['from_user_id', 'to_user_id'])
    op.create_index(op.f('ix_friend_requests_to_user_status'), 'friend_requests', ['to_user_id', 'status'], unique=False)
    op.create_index(op.f('ix_friend_requests_from_user'), 'friend_requests', ['from_user_id'], unique=False)
