import ast
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def _upgrade_enum_calls(source_path: Path) -> list[ast.Call]:
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    upgrade = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )
    return [
        node
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "ENUM"
    ]


def test_postgres_enum_migrations_disable_implicit_type_creation():
    checked_migration_count = 0
    for migration_path in sorted(MIGRATIONS_DIR.glob("*.py")):
        enum_calls = _upgrade_enum_calls(migration_path)
        if not enum_calls:
            continue
        checked_migration_count += 1
        for enum_call in enum_calls:
            create_type_keyword = next(
                (keyword for keyword in enum_call.keywords if keyword.arg == "create_type"),
                None,
            )
            assert create_type_keyword is not None, (
                f"{migration_path.name} must set create_type=False on PostgreSQL ENUM definitions"
            )
            assert isinstance(create_type_keyword.value, ast.Constant) and create_type_keyword.value.value is False, (
                f"{migration_path.name} must disable implicit enum creation in table DDL"
            )
    assert checked_migration_count > 0, "expected at least one migration with PostgreSQL enum definitions"