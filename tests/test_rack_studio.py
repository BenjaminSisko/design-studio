"""Offline Rack Studio reuse checks; Node is used only to execute plain JS."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SVG = "{http://www.w3.org/2000/svg}"


@unittest.skipUnless(shutil.which("node"), "Node is needed for renderer checks")
class RackStudioTests(unittest.TestCase):
    def runtime(self, expression: str, model: dict | None = None):
        script = r"""
const fs=require('node:fs'),vm=require('node:vm');
vm.runInThisContext(fs.readFileSync('src/rack-catalog.js','utf8'));
vm.runInThisContext(fs.readFileSync('src/rack.js','utf8'));
const model=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(EXPRESSION));
""".replace("EXPRESSION", expression)
        run = subprocess.run(["node", "-e", script], input=json.dumps(model or {}), text=True, capture_output=True, cwd=ROOT, check=True)
        return json.loads(run.stdout)

    def model(self):
        return {
            "meta": {"rackName": "Legacy name", "rackUnits": 42},
            "racks": [
                {"id": "rack-a", "name": 'Fictional rack <A> & "B"', "units": 12},
                {"id": "rack-b", "name": "Fictional rack B", "units": 20},
            ],
            "devices": [
                {"id": "device-server", "name": 'Compute <one> & "two"', "model": "dell-poweredge-r750", "type": "Hypervisor", "rackId": "rack-a", "rackU": 1, "height": 2},
                {"id": "device-switch", "name": "Switch", "model": "cisco-c9300-48p", "type": "Switch", "rackId": "rack-a", "rackU": 10, "height": 1},
                {"id": "device-storage", "name": "Storage B", "model": "synology-rs3614xs-plus", "type": "Storage", "rackId": "rack-b", "rackU": 1, "height": 2},
                {"id": "device-vm", "name": "Hosted guest", "type": "Virtual machine", "hostedBy": "device-server", "rackU": None, "height": 1},
                {"id": "device-unplaced", "name": "Unplaced instrument", "type": "Test instrument", "rackU": None, "height": 1},
            ],
        }

    def test_public_catalog_and_curated_inline_assets(self):
        result = self.runtime("({info:RACK.libraryInfo(),count:Object.keys(RACK.catalog()).length,fields:[...new Set(Object.values(RACK.catalog()).flatMap(v=>Object.keys(v)))],panels:Object.entries(RACK.catalog()).filter(([k,v])=>v.img).map(([k,v])=>({key:k,valid:!!RACK.safeImage(v.img),source:v.imageSource})),match:RACK.search('cisco 9300 48p',5),sample:RACK.describe('dell-poweredge-r750')})")
        self.assertEqual(result["count"], 5835)
        self.assertEqual(result["count"], result["info"]["modelCount"])
        # A catalog import must never bring along user layout, interface,
        # addressing, connection, notes, or other source inventory fields.
        self.assertEqual(set(result["fields"]), {"u", "kind", "mfr", "label", "role", "ports", "bays", "imageSource", "img"})
        self.assertEqual(len(result["panels"]), 9)
        self.assertTrue(all(p["valid"] and p["source"].startswith("elevation-images/") for p in result["panels"]))
        self.assertIn("cisco-c9300-48p", [item["key"] for item in result["match"]])
        self.assertEqual(result["sample"]["u"], 2)
        self.assertEqual(result["sample"]["mfr"], "Dell")
        self.assertEqual(result["info"]["sourceRevision"], "32ad450f1ca35a1e7a09b172c9817ba164f72597")

    def test_reused_front_panel_renderer_and_lowest_u(self):
        text = self.runtime("RACK.draw(model,{rackId:'rack-a'})", self.model())
        root = ET.fromstring(text)
        self.assertEqual(root.attrib["data-unit-height"], "26")
        devices = {g.attrib.get("data-id"): g for g in root.iter(SVG + "g") if "data-rack-u" in g.attrib}
        self.assertEqual(set(devices), {"device-server", "device-switch"})
        self.assertEqual(devices["device-server"].attrib["data-height-u"], "2")
        self.assertEqual(devices["device-server"].attrib["data-unit-height"], "26")
        image = devices["device-server"].find(SVG + "image")
        self.assertTrue(image.attrib["href"].startswith("data:image/png;base64,"))
        self.assertEqual(float(image.attrib["y"]), 298)  # top U2 in a 12U rack, plus 2px inset
        self.assertEqual(float(image.attrib["height"]), 48)
        title = devices["device-server"].find(SVG + "title").text
        self.assertIn('Compute <one> & "two"', title)
        self.assertIn("U1–U2", title)
        self.assertNotIn('href="http', text)
        self.assertNotIn('href="elevation-images/', text)

    def test_multiple_racks_hosting_and_selection(self):
        text = self.runtime("RACK.draw(model,{selectedId:'device-switch'})", self.model())
        root = ET.fromstring(text)
        racks = [g for g in root.iter(SVG + "g") if "data-rack-id" in g.attrib]
        self.assertEqual([g.attrib["data-rack-id"] for g in racks], ["rack-a", "rack-b"])
        ids = {g.attrib.get("data-id") for g in root.iter(SVG + "g")}
        self.assertTrue({"device-server", "device-switch", "device-storage", "device-vm", "device-unplaced"} <= ids)
        self.assertIn("Hosted by Compute", text)
        self.assertIn("Unplaced", text)
        filtered = self.runtime("RACK.draw(model,{rackId:'rack-b'})", self.model())
        self.assertIn('data-id="device-storage"', filtered)
        self.assertNotIn('data-id="device-server"', filtered)

    def test_legacy_projects_and_chassis_bays(self):
        model = {"meta": {"rackName": "Fictional 8U", "rackUnits": 8}, "devices": [
            {"id": "chassis", "name": "Node chassis", "model": "supermicro-sys-6029tp-chassis", "rackU": 1, "height": 2},
            {"id": "node", "name": "Node 1", "hostedBy": "chassis", "rackU": None, "height": 1},
        ]}
        text = self.runtime("RACK.draw(model)", model)
        root = ET.fromstring(text)
        self.assertIn("Fictional 8U", text)
        self.assertIn('data-id="node"', text)
        self.assertIn("empty", text)
        chassis = next(g for g in root.iter(SVG + "g") if g.attrib.get("data-id") == "chassis")
        self.assertIsNone(chassis.find(SVG + "image"))
        self.assertTrue(any(g.attrib.get("data-id") == "node" for g in chassis.iter(SVG + "g")))

    def test_custom_images_reject_remote_and_executable_sources(self):
        model = {"meta": {"rackUnits": 4}, "devices": [{"id": "generic", "name": "Generic", "rackU": 1, "height": 1, "panelImage": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/H1sAAAAASUVORK5CYII="}]}
        text = self.runtime("RACK.draw(model)", model)
        self.assertEqual(len(list(ET.fromstring(text).iter(SVG + "image"))), 1)
        for bad in ("https://example.invalid/device.png", "data:image/svg+xml;base64,PHN2Zz4=", "javascript:alert(1)", 'data:image/png;base64,ABC" onload="alert(1)'):
            model["devices"][0]["panelImage"] = bad
            text = self.runtime("RACK.draw(model)", model)
            self.assertEqual(len(list(ET.fromstring(text).iter(SVG + "image"))), 0)

    def test_network_stencils_are_original_inline_safe_paths(self):
        result = self.runtime("({names:RACK.stencils(),bodies:RACK.stencils().map(k=>RACK.stencil(k)),mapped:['Server','Switch','Firewall','Storage','Engineering workstation'].map(k=>RACK.stencil(k))})")
        self.assertEqual(len(result["names"]), 20)
        self.assertEqual(result["mapped"][2], result["bodies"][result["names"].index("wall-fire")])
        for body in result["bodies"] + result["mapped"]:
            root = ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg">' + body + '</svg>')
            self.assertTrue(list(root))
            self.assertTrue(all(child.tag == SVG + "path" for child in root))
            self.assertNotIn("href", body)
            self.assertNotIn("<script", body)


if __name__ == "__main__":
    unittest.main()
