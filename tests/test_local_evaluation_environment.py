from evaluation.local_environment import _update_env


def test_environment_update_removes_stale_duplicate_managed_keys(tmp_path) -> None:
    env_file = tmp_path / ".env.evaluation"
    env_file.write_text(
        "EVAL_DATABASE_ENGINE=mysql\n"
        "UNCHANGED=value\n"
        "EVAL_DATABASE_ENGINE=sql_server_old\n",
        encoding="utf-8",
    )

    _update_env(env_file, {"EVAL_DATABASE_ENGINE": "sql_server"})

    lines = env_file.read_text(encoding="utf-8").splitlines()
    assert lines.count("EVAL_DATABASE_ENGINE=sql_server") == 1
    assert not any("sql_server_old" in line for line in lines)
    assert "UNCHANGED=value" in lines
