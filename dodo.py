from __future__ import annotations


def task_install():
    return {
        "actions": ["pip install -e ."],
        "verbosity": 2,
    }


def task_test_core():
    return {
        "actions": ["pytest -m core"],
        "verbosity": 2,
    }


def task_test_acp():
    return {
        "actions": ["pytest -m acp"],
        "verbosity": 2,
    }


def task_test_unit():
    return {
        "actions": None,
        "task_dep": ["test_core", "test_acp"],
    }


def task_test_all():
    return {
        "actions": ["pytest"],
        "verbosity": 2,
    }
