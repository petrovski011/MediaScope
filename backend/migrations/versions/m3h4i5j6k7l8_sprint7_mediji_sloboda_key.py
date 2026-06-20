"""Sprint 7: standardizacija ključa MEDIJI_SLOBODA → MEDIJSKE_SLOBODE

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-06-21
"""
from alembic import op

revision = "m3h4i5j6k7l8"
down_revision = "l2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Obezbedi da nova tema postoji (idempotentno)
    op.execute("""
        INSERT INTO topics (key, label_sr, is_active)
        SELECT 'MEDIJSKE_SLOBODE', 'Medijske slobode', TRUE
        WHERE NOT EXISTS (SELECT 1 FROM topics WHERE key = 'MEDIJSKE_SLOBODE')
    """)
    # Premapiraj analizu (primary_topic je string ključ)
    op.execute("UPDATE article_analysis SET primary_topic = 'MEDIJSKE_SLOBODE' WHERE primary_topic = 'MEDIJI_SLOBODA'")
    # Premapiraj framing tipove i predloge sa stare na novu temu (ako ih ima)
    op.execute("""
        UPDATE framing_types SET topic_id = (SELECT id FROM topics WHERE key = 'MEDIJSKE_SLOBODE')
        WHERE topic_id = (SELECT id FROM topics WHERE key = 'MEDIJI_SLOBODA')
    """)
    op.execute("""
        UPDATE framing_type_proposals SET topic_id = (SELECT id FROM topics WHERE key = 'MEDIJSKE_SLOBODE')
        WHERE topic_id = (SELECT id FROM topics WHERE key = 'MEDIJI_SLOBODA')
    """)
    # Ukloni staru temu
    op.execute("DELETE FROM topics WHERE key = 'MEDIJI_SLOBODA'")


def downgrade() -> None:
    # Nepovratna konsolidacija — bez downgrade-a.
    pass
