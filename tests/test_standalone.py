#!/usr/bin/env python3
"""Packaging checks. These do not substitute for real browser/device execution."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import patch

from soso.site import build_standalone as builder

REPO = Path(__file__).resolve().parents[1]
PROJECT = Path(os.environ.get("SO_PROJECT_ROOT", REPO)).resolve()
RUNTIME = REPO / "soso/site/standalone"


class Inspector(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids = []; self.routes = []; self.resources = []; self.details = 0
        self.ignored = 0; self.words = []
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in {"script", "style"}: self.ignored += 1
        if "id" in a: self.ids.append(a["id"])
        if "data-so-page" in a: self.routes.append((a["data-so-page"], a.get("data-so-fragment", "")))
        if tag == "details": self.details += 1
        for key in ["src", "poster"]:
            if key in a: self.resources.append(a[key])
        if tag == "link" and "stylesheet" in a.get("rel", ""): self.resources.append(a.get("href", ""))
    def handle_endtag(self, tag):
        if tag in {"script", "style"}: self.ignored -= 1
    def handle_data(self, data):
        if not self.ignored: self.words.append(data)
    @property
    def text(self): return re.sub(r"\s+", " ", "".join(self.words)).strip()


class StandaloneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = {ev: builder.build(PROJECT, ev) for ev in [e["slug"] for e in builder.discover(PROJECT)]}

    def test_deterministic_and_source_bytes(self):
        for ev, (output, stats, bundle) in self.outputs.items():
            again, second, _ = builder.build(PROJECT, ev)
            self.assertEqual(output, again)
            self.assertEqual(stats, second)
            self.assertEqual(stats["sha256"], hashlib.sha256(output).hexdigest())
            self.assertNotIn(str(PROJECT).encode(), output)
            root = PROJECT/"events"/ev/"2027"
            for rel, record in bundle["sources"].items():
                self.assertEqual(record["sha256"], hashlib.sha256((root/rel).read_bytes()).hexdigest())

    def test_all_pages_text_assets_and_fragment_routes(self):
        for ev, (output, _, bundle) in self.outputs.items():
            root = PROJECT/"events"/ev/"2027"
            parsed = {name: Inspector(p["html"]) for name, p in bundle["pages"].items()}
            self.assertEqual(set(parsed), {p.relative_to(root).as_posix() for p in (root/"web").rglob("*.html")} | {"index.html"})
            for name, page in parsed.items():
                original_html = (root/name).read_text()
                if name == bundle["entry"]:
                    section = builder.licensing_section(PROJECT)
                    self.assertEqual(bundle["pages"][name]["html"].count(section), 1)
                    original_html = original_html.replace("</body>", section + "</body>", 1)
                original = Inspector(original_html)
                self.assertEqual(page.text, original.text, name)
                self.assertEqual(page.ids, original.ids, name)
                self.assertEqual(page.details, original.details, name)
                self.assertEqual(len(page.ids), len(set(page.ids)), name)
                for target, fragment in page.routes:
                    self.assertIn(target, parsed)
                    if fragment: self.assertIn(fragment, parsed[target].ids, (name, target, fragment))
                for resource in page.resources:
                    self.assertTrue(resource.startswith(("__SO_ASSET_", "data:")), resource)
                for asset_id in re.findall(r"__SO_ASSET_([a-f0-9]{64})__", bundle["pages"][name]["html"]):
                    self.assertIn(asset_id, bundle["assets"])
            for item in bundle["assets"].values():
                if "text" in item:
                    for asset_id in re.findall(r"__SO_ASSET_([a-f0-9]{64})__", item["text"]):
                        self.assertIn(asset_id, bundle["assets"])
                else:
                    base64.b64decode(item["base64"], validate=True)
            serialized = re.search(rb'<script id="bundle-data" type="application/json">(.*?)</script>', output, re.S).group(1)
            self.assertEqual(json.loads(serialized), bundle)

    def test_pdfs_are_opt_in_and_exam_label_is_plain(self):
        for ev, (_, stats, default) in self.outputs.items():
            self.assertEqual(stats["included_pdfs"], 0)
            self.assertEqual(default["pdfs"], [])
            self.assertFalse(any(a["mime"] == "application/pdf" for a in default["assets"].values()))
            _, _, included = builder.build(PROJECT, ev, include_pdfs=True)
            event = next(item for item in builder.discover(PROJECT) if item["slug"] == ev)
            expected_pdfs = {doc["pdf"] for doc in event["documents"].values() if doc.get("pdf")}
            self.assertEqual({pdf["filename"] for pdf in included["pdfs"]}, expected_pdfs)
            self.assertEqual(len(included["pdfs"]), len(expected_pdfs))
            for pdf in included["pdfs"]:
                actual = base64.b64decode(included["assets"][pdf["asset"]]["base64"])
                expected = (PROJECT/"events"/ev/"2027"/pdf["filename"]).read_bytes()
                self.assertEqual(actual, expected)
                if pdf["filename"] == "exam-reference.pdf": self.assertEqual(pdf["name"], "Exam reference")

    def test_cli_defaults_to_build_directory_and_does_not_clobber(self):
        command = [sys.executable, str(REPO/"scripts/build_standalone.py"), "thermodynamics-b", "--project-root", str(PROJECT)]
        with tempfile.TemporaryDirectory(prefix="standalone-cli-") as folder:
            with patch.object(builder, "ROOT", Path(folder)), redirect_stderr(StringIO()):
                builder.main(["thermodynamics-b", "--project-root", str(PROJECT)])
                default = Path(folder)/"build/standalone/thermodynamics-b-2027-standalone.html"
                self.assertEqual(default.read_bytes(), self.outputs["thermodynamics-b"][0])
                with self.assertRaises(SystemExit):
                    builder.main(["thermodynamics-b", "--project-root", str(PROJECT)])
            existing = Path(folder)/"existing.html"; existing.write_text("user content")
            result = subprocess.run(command+["--output", str(existing)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(existing.read_text(), "user content")
            destination = Path(folder)/"new.html"
            result = subprocess.run(command+["--output", str(destination)], capture_output=True, check=True)
            self.assertEqual(destination.read_bytes(), self.outputs["thermodynamics-b"][0])
            stdout = subprocess.run(command+["--stdout"], capture_output=True, check=True)
            self.assertEqual(stdout.stdout, destination.read_bytes())
            self.assertEqual(json.loads(stdout.stderr)["output_bytes"], len(stdout.stdout))
        self.assertFalse(Path(folder).exists())
        target = PROJECT/"this-is-not-a-distribution.html"
        self.assertFalse(target.exists())
        result = subprocess.run(command+["--output", str(target)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())

    def test_invalid_dependencies_fail_before_output(self):
        cases = [
            ('<img src="https://example.invalid/image.png">', {}),
            ('<img src="../../../../private.png">', {}),
            ('<img src="missing.png">', {}),
            ('<script type="module" src="main.js"></script>', {"main.js": "export const value=1;"}),
            ('<script src="main.js"></script>', {"main.js": "fetch('outside.json');"}),
            ('<link rel="stylesheet" href="main.css">', {"main.css": "@import 'outside.css';"}),
        ]
        for markup, files in cases:
            with tempfile.TemporaryDirectory(prefix="standalone-bad-") as folder:
                root = Path(folder); web = root/"events/solar-system-b/2027/web"; web.mkdir(parents=True)
                (web/"index.html").write_text("<!doctype html><html><body>"+markup+"</body></html>")
                for name, text in files.items(): (web/name).write_text(text)
                with self.assertRaises(builder.BuildError): builder.build(root, "solar-system-b")

    @unittest.skipUnless(shutil.which("node"), "Node is only needed for JavaScript unit checks")
    def test_javascript_syntax_and_reader_state_units(self):
        for filename in ["reader.js", "bridge.js"]:
            subprocess.run(["node", "--check", str(RUNTIME/filename)], check=True, capture_output=True)
        subprocess.run(["node", str(REPO/"tests/reader_state_test.cjs"), str(RUNTIME)], check=True, capture_output=True)
        with tempfile.TemporaryDirectory(prefix="standalone-js-") as folder:
            path = Path(folder)/"embedded.js"
            for _, _, bundle in self.outputs.values():
                for asset in bundle["assets"].values():
                    if asset["mime"] == "text/javascript":
                        path.write_bytes(base64.b64decode(asset["base64"]))
                        subprocess.run(["node", "--check", str(path)], check=True, capture_output=True)

    @unittest.skipUnless(shutil.which("node"), "Node is only needed for model calculation tests")
    def test_embedded_control_calculations(self):
        with tempfile.TemporaryDirectory(prefix="standalone-controls-") as folder:
            root = Path(folder)
            for ev, (_, _, bundle) in self.outputs.items():
                for rel, source in bundle["sources"].items():
                    if not rel.endswith(".js"): continue
                    original = (PROJECT/"events"/ev/"2027"/rel).read_bytes()
                    matched = [base64.b64decode(item["base64"]) for item in bundle["assets"].values()
                               if item["mime"] == "text/javascript" and "base64" in item]
                    self.assertIn(original, matched)
                    if ev == "thermodynamics-b" and "/interactives/" in rel:
                        (root/Path(rel).name).write_bytes(original)
                    if ev == "solar-system-b" and rel == "web/guide.js":
                        (root/"solar-guide.js").write_bytes(original)
            subprocess.run(["node", str(REPO/"tests/reader_state_test.cjs"), str(RUNTIME),
                            str(root)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)

