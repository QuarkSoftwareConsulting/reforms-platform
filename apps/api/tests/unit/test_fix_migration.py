"""El arreglo de migraciones de `scripts/fix_migration.py`."""

import ast

from scripts.fix_migration import add_enum_drops

MIGRATION = """
def upgrade() -> None:
    op.create_table('t', sa.Column('e', sa.Enum({values}), nullable=False))


def downgrade() -> None:
    op.drop_table('t')
"""


def drop_loop(fixed: str) -> tuple[str, ...]:
    """Lo que recorre de verdad el bucle generado en el `downgrade`."""
    line = next(row for row in fixed.splitlines() if "for enum_name in" in row)
    return tuple(ast.literal_eval(line.split(" in ", 1)[1].rstrip(":")))


def test_a_single_enum_is_dropped_by_name_not_letter_by_letter() -> None:
    # `("flag_environment")` es un str: el bucle borraba "f", "l", "a"... y el tipo no.
    fixed, _ = add_enum_drops(MIGRATION.format(values="'dev', 'prod', name='flag_environment'"))

    assert drop_loop(fixed) == ("flag_environment",)
