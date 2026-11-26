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
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("candidate", ROOT / "blebox_wiked_install_0.1.5.py")
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

    def test_entity_names_do_not_shadow_translations(self):
        # Exercise the actual constructors. HA's Entity._name_internal gives
        # _attr_name precedence even when explicitly set to None.
        class Coordinator:
            def __init__(self, coordinator):
                self.coordinator = coordinator

        names = ("BinarySensorEntity", "ButtonEntity", "LightEntity",
                 "RestoreNumber", "SwitchEntity", "EventEntity")
        ns = {name: type(name, (), {}) for name in names}
        ns.update(CoordinatorEntity=Coordinator, DeviceInfo=dict, DOMAIN="blebox",
                  BinarySensorDeviceClass=SimpleNamespace(LOCK="lock"),
                  ColorMode=SimpleNamespace(ONOFF="onoff"))
        for source in (installer.PAYLOAD, installer.INPUT_PAYLOAD):
            classes = [node for node in ast.parse(source).body
                       if isinstance(node, ast.ClassDef)
                       and node.name not in ("WikedCoordinator", "InputEvents")]
            exec(compile(ast.Module(body=classes, type_ignores=[]), "<entities>", "exec"), ns)
        box = SimpleNamespace(unique_id="test", name="Front",
                              firmware_version="0.1060", address="192.0.2.1")
        coordinator = SimpleNamespace(
            native=SimpleNamespace(box=box),
            addons={0: {"name": "LED 1"}, 1: {"name": "LED 2"},
                    2: {"name": "LED 3"}, 3: {"name": "Button"}, 4: {"name": "S2"}},
            input_events=SimpleNamespace())
        cases = [
            ("switch", ns["WikedSettingsSwitch"](coordinator, 3), "addon_3", "Przycisk pochwytu", "Handle button"),
            ("binary_sensor", ns["WikedBolt"](coordinator, 4), "addon_4", "S2", "S2"),
            ("binary_sensor", ns["WikedS1"](coordinator), "s1", "S1", "S1"),
            ("button", ns["WikedRelease"](coordinator, None), "release", "Elektrozaczep", "Door release"),
            ("button", ns["WikedConfigureInputs"](coordinator), "configure_inputs", "Skonfiguruj zdarzenia wejściowe", "Configure input events"),
        ]
        for i in range(3):
            led = f"LED {i+1}"
            cases.extend([
                ("number", ns["WikedDuration"](coordinator, i), f"duration_{i}", f"{led} czas świecenia", f"{led} lighting duration"),
                ("button", ns["WikedTimedLight"](coordinator, i), f"timed_{i}", f"{led} czasowo", f"{led} timed activation"),
            ])
            light = ns["WikedLight"](coordinator, i)
            self.assertEqual(light._attr_name, led)
            self.assertEqual(light._attr_unique_id, f"test_wiked_addon_{i}")
        for i in range(2):
            cases.append(("event", ns["WikedInputEvent"](coordinator, i), f"input_{i}", f"IN{i+1}", f"IN{i+1}"))
        for platform, entity, suffix, pl, en in cases:
            with self.subTest(entity=suffix):
                self.assertFalse(hasattr(entity, "_attr_name"))
                self.assertEqual(entity._attr_unique_id, f"test_wiked_{suffix}")
                for lang, expected in (("pl", pl), ("en", en)):
                    name = installer.TRANSLATIONS[lang]["entity"][platform][entity._attr_translation_key]["name"]
                    self.assertEqual(name.format(**getattr(entity, "_attr_translation_placeholders", {})), expected)

    def test_translation_conflict(self):
        with self.assertRaises(RuntimeError):
            installer.merge_translations({"name": "native"}, {"name": "replacement"})


if __name__ == "__main__":
    unittest.main()
