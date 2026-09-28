"""Tests for the pre-commit hook helpers. Run from the repo root: python -m unittest discover -s .claude/hooks"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import pre_commit_sp_check as hook  # noqa: E402


class IsGitCommit(unittest.TestCase):
    def test_plain_commit(self):
        self.assertTrue(hook._is_git_commit_command('git commit -m "x"'))

    def test_commit_after_add(self):
        self.assertTrue(hook._is_git_commit_command('git add a.py && git commit -m "x"'))
        self.assertTrue(hook._is_git_commit_command("git add -A; git commit -m x"))
        self.assertTrue(hook._is_git_commit_command("git add a || git commit -m x"))
        self.assertTrue(hook._is_git_commit_command("git add a\ngit commit -m x"))

    def test_global_options_before_subcommand(self):
        self.assertTrue(hook._is_git_commit_command("git -C /tmp/repo -c user.name=x commit -m x"))

    def test_non_commit(self):
        self.assertFalse(hook._is_git_commit_command("git status"))
        self.assertFalse(hook._is_git_commit_command("git add a.py && git push"))
        self.assertFalse(hook._is_git_commit_command("ls -la"))

    def test_commit_word_inside_message_is_not_a_commit(self):
        self.assertFalse(hook._is_git_commit_command('git log --grep "git commit"'))
        self.assertFalse(hook._is_git_commit_command('echo "run git commit later"'))

    def test_multiline_message_stays_one_command(self):
        self.assertTrue(hook._is_git_commit_command('git commit -m "line one\nline two"'))
        self.assertFalse(hook._is_git_commit_command('git log --grep "a\ngit commit b"'))


class AddedLines(unittest.TestCase):
    DIFF = (
        "--- a/x.py\n+++ b/x.py\n@@\n+try:\n+    pass\n+except Exception as e:\n"
        "--- a/notes.md\n+++ b/notes.md\n@@\n+        except Exception as e:\n"
    )

    def test_pairs_lines_with_files(self):
        pairs = hook._added_lines_by_file(self.DIFF)
        self.assertIn(("x.py", "+except Exception as e:"), pairs)
        self.assertIn(("notes.md", "+        except Exception as e:"), pairs)
        self.assertFalse(any(line.startswith("+++") for _, line in pairs))


class EndToEnd(unittest.TestCase):
    def run_hook(self, command, cwd):
        payload = json.dumps({"tool_input": {"command": command}})
        return subprocess.run([sys.executable, hook.__file__], input=payload, capture_output=True,
                              text=True, cwd=cwd)

    def test_warning_is_json_system_message_and_python_only(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args):
                subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True)
            git("init", "-q")
            with open(os.path.join(tmp, "notes.md"), "w") as f:
                f.write("    except Exception as e:\n")
            git("add", "notes.md")
            out = self.run_hook("git commit -m x", tmp)
            self.assertEqual(out.returncode, 0)
            self.assertEqual(out.stdout.strip(), "")  # markdown example must not warn

            with open(os.path.join(tmp, "a.py"), "w") as f:
                f.write("try:\n    pass\nexcept Exception:\n    pass\n")
            git("add", "a.py")
            out = self.run_hook("git add a.py && git commit -m x", tmp)
            self.assertEqual(out.returncode, 0)
            data = json.loads(out.stdout)
            self.assertIn("except Exception", data["systemMessage"])
            self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "PreToolUse")


if __name__ == "__main__":
    unittest.main()
