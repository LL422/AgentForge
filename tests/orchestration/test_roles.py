# tests/orchestration/test_roles.py
from nanobot.orchestration.roles import WORKER_ROLES


def test_all_roles_have_required_keys():
    for role_name, role_def in WORKER_ROLES.items():
        assert "display_name" in role_def, f"{role_name} missing display_name"
        assert "tools" in role_def, f"{role_name} missing tools"
        assert "system_prompt" in role_def, f"{role_name} missing system_prompt"


def test_analyst_is_read_only():
    analyst = WORKER_ROLES["analyst"]
    write_tools = {"write_file", "edit_file"}
    assert not write_tools.intersection(analyst["tools"])


def test_reviewer_is_read_only():
    reviewer = WORKER_ROLES["reviewer"]
    write_tools = {"write_file", "edit_file"}
    assert not write_tools.intersection(reviewer["tools"])


def test_developer_can_write():
    developer = WORKER_ROLES["developer"]
    assert "write_file" in developer["tools"]
    assert "edit_file" in developer["tools"]


def test_all_role_names_are_valid_keys():
    valid_roles = {"analyst", "developer", "reviewer", "tester"}
    assert set(WORKER_ROLES.keys()) == valid_roles
