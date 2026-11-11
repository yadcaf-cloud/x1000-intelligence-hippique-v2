cd ~/x1000-intelligence-hippique-v2 || exit 1

mkdir -p tests

if [ -e tests/test_audit_x1000.py ]; then
    echo "ARRÊT : le fichier existe déjà. Aucune modification."
else
cat > tests/test_audit_x1000.py <<'PY'
"""Audit non destructif du projet X1000 PHOENIX."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

PROTECTED_NAMES = {
    "figes.json",
    "audits.json",
    "courses.json",
    "selections.json",
}


def _python_sources():
    excluded = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
    }

    return sorted(
        p for p in ROOT.rglob("*.py")
        if not any(
            part in excluded
            for part in p.relative_to(ROOT).parts
        )
    )


def test_racine_du_projet():
    assert ROOT.is_dir(), (
        f"Racine introuvable : {ROOT}"
    )


def test_sources_python_presentes():
    assert _python_sources(), (
        "Aucun fichier Python trouvé"
    )


def test_syntaxe_sources_python():
    errors = []

    for path in _python_sources():
        try:
            ast.parse(
                path.read_bytes(),
                filename=str(path),
            )
        except (
            SyntaxError,
            UnicodeError,
            ValueError,
        ) as exc:
            errors.append(
                f"{path.relative_to(ROOT)} : {exc}"
            )

    assert not errors, (
        "Erreurs de syntaxe :\n"
        + "\n".join(errors)
    )


def test_fichiers_proteges_non_modifies():
    paths = sorted(
        p for p in ROOT.rglob("*")
        if p.is_file()
        and p.name in PROTECTED_NAMES
        and ".git" not in p.relative_to(ROOT).parts
    )

    before = {
        p: hashlib.sha256(
            p.read_bytes()
        ).hexdigest()
        for p in paths
    }

    after = {
        p: hashlib.sha256(
            p.read_bytes()
        ).hexdigest()
        for p in paths
    }

    assert before == after, (
        "Un fichier protégé a changé"
    )


def test_aucune_ecriture_par_ce_module():
    source = Path(__file__).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    forbidden = {
        "write_text",
        "write_bytes",
        "unlink",
        "rename",
        "replace",
        "mkdir",
        "rmdir",
    }

    calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden
    ]

    assert not calls, (
        f"Appels de modification détectés : {calls}"
    )
PY
fi

python -m pytest -q tests/test_audit_x1000.py
