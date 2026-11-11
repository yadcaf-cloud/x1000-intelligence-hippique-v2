"""X1000 PHOENIX — Tests de réparation non destructifs."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

EXCLUDED = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}


def python_sources():
    return sorted(
        p for p in ROOT.rglob("*.py")
        if not any(
            part in EXCLUDED
            for part in p.relative_to(ROOT).parts
        )
    )


def test_racine_x1000():
    assert ROOT.is_dir()


def test_sources_python_presentes():
    assert python_sources(), "Aucune source Python"


@pytest.mark.parametrize(
    "source",
    python_sources(),
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_syntaxe_python(source):
    contenu = source.read_text(encoding="utf-8")
    ast.parse(contenu, filename=str(source))


def test_archives_protegees():
    """Vérification sans écriture ni suppression."""
    protected = {
        "figes.json",
        "audits.json",
        "courses.json",
        "selections.json",
    }

    for name in protected:
        for fichier in ROOT.rglob(name):
            assert fichier.is_file()
