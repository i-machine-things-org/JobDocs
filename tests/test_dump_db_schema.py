"""Tests for tools/dump_db_schema.py's settings-merging and formula-injection
guard -- both added fixing CodeRabbit findings on PR #343 against a prior,
buggier version of this file:

- _load_settings() used to return EITHER env vars OR settings.json, whole --
  a lone JOBBOSS_DB_PASS (the documented way to run this with a different
  login against the same server) silently made every other JOBBOSS_DB_* env
  var and all of settings.json invisible, since any one of HOST/PORT/NAME/
  USER being unset in that mode just produced blank strings instead of
  falling back to the stored value.
- Table/column identifier cells were written to the workbook unneutralized,
  the same formula-injection risk already fixed for report exports in
  modules/reporting/module.py.

Pure functions -- no real DB, no real settings.json (get_config_dir() is
monkeypatched to a tmp_path).
"""

import json

import tools.dump_db_schema as dump_db_schema


def test_neutralize_prefixes_formula_trigger_chars():
    for char in ('=', '+', '-', '@', '\t', '\r'):
        value = f"{char}cmd|/c calc"
        assert dump_db_schema._neutralize_formula_cell(value) == f"'{value}"


def test_neutralize_leaves_ordinary_identifiers_untouched():
    assert dump_db_schema._neutralize_formula_cell("Job_Operation") == "Job_Operation"
    assert dump_db_schema._neutralize_formula_cell("dbo") == "dbo"


def test_neutralize_leaves_non_string_values_untouched():
    # ORDINAL_POSITION/CHARACTER_MAXIMUM_LENGTH are ints or None -- never
    # passed through this guard by the caller, but it must not crash if it
    # ever is.
    assert dump_db_schema._neutralize_formula_cell(5) == 5
    assert dump_db_schema._neutralize_formula_cell(None) is None


def test_load_settings_falls_back_to_settings_json(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({
        'jobboss_db_host': 'sqlserver01', 'jobboss_db_port': '1433',
        'jobboss_db_name': 'JobBOSS', 'jobboss_db_user': 'jobdocs_ro',
    }))
    monkeypatch.setattr(dump_db_schema, 'get_config_dir', lambda: tmp_path)
    for var in ('JOBBOSS_DB_HOST', 'JOBBOSS_DB_PORT', 'JOBBOSS_DB_NAME', 'JOBBOSS_DB_USER'):
        monkeypatch.delenv(var, raising=False)

    settings = dump_db_schema._load_settings()
    assert settings['jobboss_db_host'] == 'sqlserver01'
    assert settings['jobboss_db_user'] == 'jobdocs_ro'


def test_load_settings_env_var_overrides_one_field_without_blanking_the_rest(tmp_path, monkeypatch):
    # The exact bug: JOBBOSS_DB_USER alone (e.g. to connect as a different,
    # broader login) must not blank out HOST/NAME, which still come from
    # settings.json.
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({
        'jobboss_db_host': 'sqlserver01', 'jobboss_db_port': '1433',
        'jobboss_db_name': 'JobBOSS', 'jobboss_db_user': 'jobdocs_ro',
    }))
    monkeypatch.setattr(dump_db_schema, 'get_config_dir', lambda: tmp_path)
    monkeypatch.setenv('JOBBOSS_DB_USER', 'dba_login')
    for var in ('JOBBOSS_DB_HOST', 'JOBBOSS_DB_PORT', 'JOBBOSS_DB_NAME'):
        monkeypatch.delenv(var, raising=False)

    settings = dump_db_schema._load_settings()
    assert settings['jobboss_db_host'] == 'sqlserver01'  # from settings.json, NOT blanked
    assert settings['jobboss_db_name'] == 'JobBOSS'       # from settings.json, NOT blanked
    assert settings['jobboss_db_user'] == 'dba_login'     # overridden by env var


def test_load_settings_env_vars_work_with_no_settings_json_at_all(tmp_path, monkeypatch):
    monkeypatch.setattr(dump_db_schema, 'get_config_dir', lambda: tmp_path)  # no settings.json here
    monkeypatch.setenv('JOBBOSS_DB_HOST', 'otherserver')
    monkeypatch.setenv('JOBBOSS_DB_NAME', 'JobBOSS')
    monkeypatch.setenv('JOBBOSS_DB_USER', 'tempuser')
    monkeypatch.delenv('JOBBOSS_DB_PORT', raising=False)

    settings = dump_db_schema._load_settings()
    assert settings['jobboss_db_host'] == 'otherserver'
    assert settings['jobboss_db_user'] == 'tempuser'


def test_load_settings_returns_empty_dict_when_nothing_is_configured(tmp_path, monkeypatch):
    # No exception here -- main() is the one place that validates and raises
    # a friendly SystemExit now, not _load_settings() itself.
    monkeypatch.setattr(dump_db_schema, 'get_config_dir', lambda: tmp_path)
    for var in ('JOBBOSS_DB_HOST', 'JOBBOSS_DB_PORT', 'JOBBOSS_DB_NAME', 'JOBBOSS_DB_USER'):
        monkeypatch.delenv(var, raising=False)

    assert dump_db_schema._load_settings() == {}
