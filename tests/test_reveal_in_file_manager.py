"""Tests for shared/utils.py's reveal_in_file_manager (subprocess + filesystem)."""

from unittest.mock import patch

from shared.utils import reveal_in_file_manager


def test_missing_path_reports_not_found(tmp_path):
    missing = tmp_path / "does-not-exist"
    success, error = reveal_in_file_manager(str(missing))
    assert success is False
    assert "Not found" in error


def test_windows_uses_a_command_string_not_a_list(tmp_path):
    # Regression test: a space in the target (e.g. "New folder", the exact
    # kind of entry this feature flags) must not break explorer's /select.
    # Popen's list form auto-quotes the whole "/select,<path>" token when the
    # path has a space, which explorer's parser doesn't understand -- it
    # silently opens the default library (Documents) instead. Passing a
    # single command-line string, quoting only the path, is the form
    # explorer actually understands.
    target = tmp_path / "New folder"
    target.mkdir()

    with patch("shared.utils.platform.system", return_value="Windows"), \
         patch("shared.utils.subprocess.Popen") as mock_popen:
        success, error = reveal_in_file_manager(str(target))

    assert success is True
    assert error is None
    mock_popen.assert_called_once()
    (call_arg,), _ = mock_popen.call_args
    assert isinstance(call_arg, str), "must be a single command-line string, not an argv list"
    assert call_arg == f'explorer /select,"{target}"'


def test_macos_uses_open_dash_r(tmp_path):
    target = tmp_path / "some folder"
    target.mkdir()

    with patch("shared.utils.platform.system", return_value="Darwin"), \
         patch("shared.utils.subprocess.Popen") as mock_popen:
        success, error = reveal_in_file_manager(str(target))

    assert success is True
    assert error is None
    mock_popen.assert_called_once_with(["open", "-R", str(target)])


def test_linux_falls_back_to_opening_parent_dir(tmp_path):
    target = tmp_path / "some folder"
    target.mkdir()

    with patch("shared.utils.platform.system", return_value="Linux"), \
         patch("shared.utils.subprocess.Popen") as mock_popen:
        success, error = reveal_in_file_manager(str(target))

    assert success is True
    assert error is None
    mock_popen.assert_called_once_with(["xdg-open", str(tmp_path)])


def test_linux_resolves_a_relative_path_before_taking_its_dirname(tmp_path, monkeypatch):
    # CodeRabbit finding, PR #329: a relative path's os.path.dirname() can
    # be '' (e.g. dirname('folder') == ''), which hands xdg-open an empty
    # operand -- and since Popen() doesn't wait for the child, that failure
    # is invisible; the function still reports success.
    target_name = "some folder"
    (tmp_path / target_name).mkdir()
    monkeypatch.chdir(tmp_path)

    with patch("shared.utils.platform.system", return_value="Linux"), \
         patch("shared.utils.subprocess.Popen") as mock_popen:
        success, error = reveal_in_file_manager(target_name)

    assert success is True
    assert error is None
    # If norm_path stayed relative, dirname(target_name) would be '' --
    # asserting the real absolute parent proves it was resolved first.
    mock_popen.assert_called_once_with(["xdg-open", str(tmp_path)])
