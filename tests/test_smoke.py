import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

INSTALLER = Path(__file__).resolve().parents[1] / 'blebox_wiked_install_0.1.4.py'
spec = importlib.util.spec_from_file_location('installer', INSTALLER)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

# Extract real implementations without importing Home Assistant dependencies.
class Base:
    def __init__(self, *args, **kwargs):
        pass
class BinarySensorEntity:
    pass
ns = dict(WikedEntity=Base, AddonEntity=Base, BinarySensorEntity=BinarySensorEntity,
          BinarySensorDeviceClass=SimpleNamespace(LOCK='lock'))
tree = ast.parse(installer.PAYLOAD)
names = {'get_addons','state_map','bit','WikedS1','WikedBolt'}
exec(compile(ast.Module(body=[node for node in tree.body if getattr(node,'name',None) in names], type_ignores=[]), '<isolated payload>', 'exec'),ns)

class SmokeTests(unittest.TestCase):
    def test_syntax(self):
        compile(installer.PAYLOAD, '<payload>', 'exec')
    def test_discovery(self):
        self.assertEqual(set(ns['get_addons']({'addons':[{'id':7,'type':'switch'},{'id':4,'type':'sensor'},{'id':8,'type':'unknown'},{'id':True,'type':'switch'}]})),{7,4})
    def test_state_map(self):
        data=ns['state_map']({'gate':{'currentPos':100},'addons':[{'id':4,'sensor':{'value':0}}]})
        self.assertEqual(data['gate']['currentPos'],100)
        self.assertEqual(data[4]['sensor']['value'],0)
    def test_invalid_response(self):
        with self.assertRaises(ValueError): ns['state_map']({'gate':{}})
    def test_bit_validation(self):
        for value, expected in [(0,False),(1,True),(2,None),(True,None),(None,None)]:
            self.assertIs(ns['bit']({'relay':{'state':value}},'relay','state'),expected)
    def test_independent_inputs(self):
        for pos, bolt in [(0,0),(100,0),(100,1),(0,1)]:
            s1=ns['WikedS1'](None); s1.coordinator=SimpleNamespace(data={'gate':{'currentPos':pos}})
            s2=object.__new__(ns['WikedBolt']); s2.addon_state={'sensor':{'value':bolt}}
            self.assertIs(s1.is_on,pos==100)
            self.assertIs(s2.is_on,bolt==0)
    def test_unknown_states(self):
        s1=ns['WikedS1'](None); s1.coordinator=SimpleNamespace(data={'gate':{'currentPos':50}})
        s2=object.__new__(ns['WikedBolt']); s2.addon_state={'sensor':{}}
        self.assertIsNone(s1.is_on); self.assertIsNone(s2.is_on)
    def test_refuse_unrelated_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp); (config/'configuration.yaml').touch()
            dest=config/'custom_components'/'blebox'; dest.mkdir(parents=True)
            marker=dest/'keep.txt'; marker.write_text('keep')
            for flag in ('--upgrade','--remove'):
                p=subprocess.run([sys.executable,str(INSTALLER),'--config',tmp,flag],capture_output=True,text=True)
                self.assertNotEqual(p.returncode,0)
                self.assertEqual(marker.read_text(),'keep')

if __name__ == '__main__': unittest.main()
