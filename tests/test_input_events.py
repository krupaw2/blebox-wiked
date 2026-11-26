"""Offline regression tests for WIKED input action provisioning."""
import ast
import importlib.util
from pathlib import Path
import unittest
from urllib.parse import urlsplit

installer_path = Path(__file__).resolve().parents[1] / "blebox_wiked_install_0.1.3.py"
spec = importlib.util.spec_from_file_location("installer_inputs", installer_path)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

names = {"INPUTS", "NAMES", "PATH", "FIELDS", "action_fields", "make_action",
         "action_map", "plan_actions", "event_type"}
tree = ast.parse(installer.INPUT_PAYLOAD)
nodes = [node for node in tree.body if getattr(node, "name", None) in names or
         isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets)]
ns = {"urlsplit": urlsplit}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "<input helpers>", "exec"), ns)


class InputTests(unittest.TestCase):
    def setUp(self):
        self.tokens = {"0": "a"*32, "1": "b"*32}
        self.urls = {i: "http://192.0.2.1:8123/api/webhook/" + self.tokens[str(i)]
                     for i in (0, 1)}
        self.actions = {i: {"id": i, "name": "", "input": 0, "triggerType": 0,
                            "actionType": 0, "param": "", "intervalS": 0, "triggerParam": 0}
                        for i in range(5)}
        self.actions[0].update(name="OPEN", input=1, triggerType=4, actionType=100,
                               param="http://localhost/s/p/conditional")
        self.actions[1].update(name="Bell", triggerType=4, actionType=52, param="Bell")
        self.actions[2].update(name="Existing action", triggerType=4, actionType=50,
                               param="http://192.0.2.2/")

    def test_syntax(self):
        compile(installer.PAYLOAD, "<base>", "exec")
        compile(installer.INPUT_PAYLOAD, "<inputs>", "exec")

    def test_preserve_actions(self):
        import copy
        old = copy.deepcopy(self.actions)
        changes = ns["plan_actions"](self.actions, self.urls, self.tokens)
        self.assertEqual(self.actions, old)
        self.assertEqual([(a["id"], a["input"], a["actionType"]) for a in changes],
                         [(3, 0, 50), (4, 1, 50)])

    def test_idempotent_and_url_update(self):
        for a in ns["plan_actions"](self.actions, self.urls, self.tokens):
            self.actions[a["id"]] = a
        self.assertEqual(ns["plan_actions"](self.actions, self.urls, self.tokens), [])
        new_urls = {i: u.replace("192.0.2.1", "192.0.2.3") for i, u in self.urls.items()}
        self.assertEqual([a["id"] for a in ns["plan_actions"](self.actions, new_urls, self.tokens)],
                         [3, 4])

    def test_no_capacity(self):
        self.actions.pop(4)
        with self.assertRaises(ValueError):
            ns["plan_actions"](self.actions, self.urls, self.tokens)

    def test_invalid_inventory(self):
        with self.assertRaises(ValueError):
            ns["action_map"]({"itemsLimit": 5, "actions": list(self.actions.values())[:-1]})
        with self.assertRaises(ValueError):
            ns["action_map"]({"itemsLimit": 5, "actions": [self.actions[0]]*5})
        self.assertEqual(ns["action_map"]({"itemsLimit": 5, "actions": list(self.actions.values())}),
                         self.actions)

    def test_handle_modes(self):
        self.assertEqual(ns["event_type"](0, None), "doorbell")
        self.assertEqual(ns["event_type"](1, False), "doorbell")
        self.assertEqual(ns["event_type"](1, True), "pressed")
        self.assertEqual(ns["event_type"](1, None), "pressed_unknown")


if __name__ == "__main__":
    unittest.main()
