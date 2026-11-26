"""Verify the standalone installer and bilingual translation assets."""
import ast
import importlib.util
import json
from pathlib import Path
import string
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("candidate", ROOT / "blebox_wiked_install_0.1.4.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, path + (key,))
    else:
        yield path, value


class TranslationTests(unittest.TestCase):
    def test_build_reproducible(self):
        subprocess.run([sys.executable, str(ROOT / "scripts/build_installer.py"), "--check"], check=True)

    def test_language_parity(self):
        en, pl = (dict(leaves(installer.TRANSLATIONS[lang])) for lang in ("en", "pl"))
        self.assertEqual(en.keys(), pl.keys())
        for key in en:
            self.assertTrue(en[key] and pl[key])
            fields = lambda value: {field for _, field, _, _ in string.Formatter().parse(value) if field}
            self.assertEqual(fields(en[key]), fields(pl[key]), key)

    def test_all_translation_keys_defined(self):
        keys = set()
        for source in (installer.PAYLOAD, installer.INPUT_PAYLOAD):
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.keyword) and node.arg == "translation_key" and isinstance(node.value, ast.Constant):
                    keys.add(node.value.value)
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                    if any(isinstance(t, ast.Attribute) and t.attr == "_attr_translation_key" for t in node.targets):
                        keys.add(node.value.value)
        self.assertGreaterEqual(len(keys), 16)
        for lang in ("en", "pl"):
            resources = installer.TRANSLATIONS[lang]
            defined = set(resources["exceptions"])
            for platform in resources["entity"].values():
                defined.update(platform)
            self.assertEqual(keys, defined)

    def test_preserve_native_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "translations").mkdir()
            for lang in ("en", "pl"):
                (root / "translations" / f"{lang}.json").write_text(json.dumps({"config": {"step": {"user": {"title": "Original"}}}, "entity": {"switch": {"native": {"name": "Native"}}}}))
            installer.install_translations(root)
            installer.install_translations(root)
            for lang in ("en", "pl"):
                data = json.loads((root / "translations" / f"{lang}.json").read_text())
                self.assertEqual(data["config"]["step"]["user"]["title"], "Original")
                self.assertEqual(data["entity"]["switch"]["native"]["name"], "Native")
                self.assertEqual(data["entity"]["switch"]["wiked_handle"], installer.TRANSLATIONS[lang]["entity"]["switch"]["wiked_handle"])

    def test_translation_conflict(self):
        with self.assertRaises(RuntimeError):
            installer.merge_translations({"name": "native"}, {"name": "replacement"})


if __name__ == "__main__":
    unittest.main()
