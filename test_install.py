#!/usr/bin/env python3
"""Offline isolated regression tests. Never uses the real DSH_HOME."""
import argparse
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
import install


class InstallerTests(unittest.TestCase):
    def setUp(self):
        # Keep fake backups outside the package, just like the documented installer contract.
        self.temp = tempfile.TemporaryDirectory(prefix=".gpt-flash-handoff-test-", dir=Path(__file__).absolute().parent.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "fake-dsh-home"
        self.backups = self.root / "fake-backups"
        self.target = self.home / "skills" / install.NAME
        self.agents = self.home / "AGENTS.md"

    def call(self, **kw):
        opts = dict(home=str(self.home), global_mode=False, disable_global=False,
                    uninstall=False, backup_dir=str(self.backups), dry_run=False, yes=False)
        opts.update(kw)
        with contextlib.redirect_stdout(io.StringIO()):
            install.run(argparse.Namespace(**opts))

    def seed(self, data):
        self.home.mkdir(parents=True, exist_ok=True)
        self.agents.write_bytes(data)

    def test_default_install_is_on_demand_and_does_not_read_global(self):
        self.seed(b"\xff\xfeunreadable-on-purpose")
        self.call()
        self.assertEqual(self.agents.read_bytes(), b"\xff\xfeunreadable-on-purpose")
        self.assertEqual(install.existing_payload(self.target), install.payload()[1])
        self.assertFalse(self.backups.exists())

    def test_install_twice_is_idempotent(self):
        self.call()
        first = install.existing_payload(self.target)
        self.call()
        self.assertEqual(first, install.existing_payload(self.target))
        self.assertFalse(self.agents.exists())

    def test_global_enable_preserves_bom_crlf_and_exact_backup(self):
        original = b"\xef\xbb\xbf# existing\r\nkeep this\r\n"
        self.seed(original)
        self.call(global_mode=True)
        after = self.agents.read_bytes()
        self.assertTrue(after.startswith(original))
        self.assertEqual(after.count(install.BEGIN), 1)
        self.assertEqual([p.read_bytes() for p in self.backups.glob("*.bak")], [original])
        self.call(global_mode=True)
        self.assertEqual(self.agents.read_bytes(), after)
        self.assertEqual(len(list(self.backups.glob("*.bak"))), 1)

    def test_disable_restores_exact_original_and_retains_skill(self):
        original = b"# user rules\r\n\r\n"
        self.seed(original)
        self.call(global_mode=True)
        self.call(disable_global=True)
        self.assertEqual(self.agents.read_bytes(), original)
        self.assertTrue((self.target / "SKILL.md").exists())

    def test_uninstall_requires_confirmation_and_restores_original(self):
        original = b"# unchanged user rules"
        self.seed(original)
        self.call(global_mode=True)
        with self.assertRaisesRegex(ValueError, "requires --yes"):
            self.call(uninstall=True)
        self.assertTrue(self.target.exists())
        self.call(uninstall=True, yes=True)
        self.assertEqual(self.agents.read_bytes(), original)
        self.assertFalse(self.target.exists())
        self.call(uninstall=True, yes=True)  # repeat is harmless

    def test_dry_run_makes_no_directories_or_writes(self):
        self.call(global_mode=True, dry_run=True)
        self.assertFalse(self.home.exists())
        self.assertFalse(self.backups.exists())

    def test_global_edit_requires_explicit_backup_directory(self):
        original = b"# existing"
        self.seed(original)
        with self.assertRaisesRegex(ValueError, "--backup-dir"):
            self.call(global_mode=True, backup_dir=None)
        self.assertEqual(self.agents.read_bytes(), original)
        self.assertFalse(self.target.exists())

    def test_unknown_global_encoding_is_refused_before_install(self):
        original = b"\xff\xfeold rules"
        self.seed(original)
        with self.assertRaises(UnicodeError):
            self.call(global_mode=True)
        self.assertEqual(self.agents.read_bytes(), original)
        self.assertFalse(self.target.exists())

    def test_edited_skill_is_not_overwritten_or_deleted(self):
        self.call()
        skill = self.target / "SKILL.md"
        skill.write_bytes(b"user modification")
        for mode in ({}, dict(uninstall=True, yes=True), dict(global_mode=True)):
            with self.assertRaisesRegex(ValueError, "differs"):
                self.call(**mode)
            self.assertEqual(skill.read_bytes(), b"user modification")
        self.assertFalse(self.agents.exists())

    def test_extra_file_prevents_uninstall(self):
        self.call()
        extra = self.target / "user-note.txt"
        extra.write_bytes(b"retain")
        with self.assertRaisesRegex(ValueError, "extra files"):
            self.call(uninstall=True, yes=True)
        self.assertEqual(extra.read_bytes(), b"retain")

    def test_incomplete_or_duplicate_markers_prevent_all_edits(self):
        for original in (install.BEGIN, install.BEGIN + install.END + install.BEGIN + install.END):
            self.seed(original)
            with self.assertRaisesRegex(ValueError, "incomplete managed"):
                self.call(global_mode=True)
            self.assertEqual(self.agents.read_bytes(), original)
            self.assertFalse(self.target.exists())

    def test_edited_global_block_is_not_overwritten_or_removed(self):
        self.call(global_mode=True)
        changed = self.agents.read_bytes().replace(b"## GPT", b"## EDITED GPT")
        self.agents.write_bytes(changed)
        for mode in (dict(global_mode=True), dict(disable_global=True), dict(uninstall=True, yes=True)):
            with self.assertRaisesRegex(ValueError, "has been edited"):
                self.call(**mode)
            self.assertEqual(self.agents.read_bytes(), changed)
            self.assertTrue(self.target.exists())

    def test_global_only_home_uninstall_and_edited_suffix_preservation(self):
        self.call(global_mode=True)
        block = install.payload()[2]
        self.assertEqual(self.agents.read_bytes(), block)
        self.agents.write_bytes(block + b"\n# added later\n")
        self.call(uninstall=True, yes=True)
        self.assertEqual(self.agents.read_bytes(), b"\n# added later\n")

    def test_backup_inside_package_or_skill_is_refused(self):
        for bad in (install.ROOT / "backups", self.target / "backup"):
            with self.assertRaisesRegex(ValueError, "outside the package"):
                self.call(backup_dir=str(bad))
        self.assertFalse(self.target.exists())

    def test_manifest_checksum_tampering_is_refused(self):
        from unittest.mock import patch
        original = install.digest
        with patch.object(install, "digest", side_effect=lambda data: "bad" if b"name:" in data else original(data)):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                self.call()
        self.assertFalse(self.target.exists())

    def test_empty_existing_skill_is_refused(self):
        self.target.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "empty Skill"):
            self.call()
        self.assertEqual(list(self.target.iterdir()), [])

    def test_path_overlap_is_refused(self):
        from unittest.mock import patch
        source, files, block = install.payload()
        # A target nested inside the payload is a real overlap; a sibling is not.
        with self.assertRaisesRegex(ValueError, "overlaps package"):
            self.call(home=str(source / "nested-home"))
        # Equality and a source nested inside the installation target are refused too.
        for simulated_source in (self.target, self.target / "nested-source"):
            with patch.object(install, "payload", return_value=(simulated_source, files, block)):
                with self.assertRaisesRegex(ValueError, "overlaps package"):
                    self.call()
        self.assertFalse(self.home.exists())

    def test_safe_rejects_symlink_or_junction(self):
        from unittest.mock import patch
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaisesRegex(ValueError, "symlink/junction"):
                self.call()
        if hasattr(Path, "is_junction"):
            with patch.object(Path, "is_junction", return_value=True):
                with self.assertRaisesRegex(ValueError, "symlink/junction"):
                    self.call()


if __name__ == "__main__":
    unittest.main(verbosity=2)
