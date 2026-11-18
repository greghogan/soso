"""Build one offline, asset-embedded event HTML without changing editable sources."""
from __future__ import annotations
import argparse
from .build_catalog import normalise_page, discover, portable_navigation, editions, DOCUMENTS
import base64
import hashlib
import html
from html.parser import HTMLParser
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import unquote, urlsplit

TOKEN = "__SO_ASSET_"
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)


class BuildError(ValueError):
    pass


class Compiler:
    def __init__(self, event_dir, include_pdfs=False):
        self.root = Path(event_dir).resolve()
        self.include_pdfs = include_pdfs
        self.assets = {}
        self.pages = {}
        self.sources = {}
        self.asset_paths = {}
        self.loading = set()
        self.pdfs = []
        self.bridge = (Path(__file__).parent / "standalone/bridge.js").read_text()
        self.pending = sorted(p.relative_to(self.root).as_posix() for p in (self.root / "web").rglob("*.html"))
        if "web/index.html" not in self.pending:
            raise BuildError("Missing web/index.html")

    def read(self, relative):
        path = self.root / relative
        try:
            path.resolve().relative_to(self.root)
        except ValueError:
            raise BuildError("Reference escapes the event directory: " + relative)
        if path.is_symlink() or not path.is_file():
            raise BuildError("Missing or symlinked runtime file: " + relative)
        data = path.read_bytes()
        self.sources[relative] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        return data

    def resolve(self, base, reference):
        url = urlsplit(html.unescape(reference.strip()))
        if url.scheme or url.netloc:
            return None, unquote(url.fragment)
        if url.query:
            raise BuildError("Query-dependent local navigation is unsupported: " + reference)
        if not url.path:
            return base, unquote(url.fragment)
        path = (self.root / base).parent / unquote(url.path)
        try:
            relative = path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            raise BuildError("Reference escapes the event directory: " + reference)
        if path.is_dir():
            relative = (Path(relative) / "index.html").as_posix()
        return relative, unquote(url.fragment)

    def token(self, asset_id, fragment=""):
        return TOKEN + asset_id + "__" + ("#" + fragment if fragment else "")

    def resource(self, base, reference):
        if reference.startswith(("data:", "#")):
            return reference
        relative, fragment = self.resolve(base, reference)
        if relative is None:
            raise BuildError("Remote runtime resource: " + reference)
        return self.token(self.asset(relative), fragment)

    def css(self, text, base):
        if re.search(r"@import\b", text, re.I):
            raise BuildError("CSS imports must be flattened before packaging: " + base)
        return CSS_URL.sub(lambda match: "url(\"" + self.resource(base, match.group(2)) + "\")", text)

    def asset(self, relative):
        if relative in self.asset_paths:
            return self.asset_paths[relative]
        if relative in self.loading:
            raise BuildError("Cyclic runtime resource: " + relative)
        self.loading.add(relative)
        data = self.read(relative)
        suffix = Path(relative).suffix.lower()
        mime = {".js": "text/javascript", ".svg": "image/svg+xml", ".css": "text/css", ".pdf": "application/pdf"}.get(
            suffix, mimetypes.guess_type(relative)[0] or "application/octet-stream")
        if suffix == ".css":
            content = self.css(data.decode("utf-8"), relative)
            record = {"mime": mime, "text": content}
            key_data = content.encode("utf-8")
        else:
            if suffix == ".js" and re.search(r"\b(?:fetch\s*\(|XMLHttpRequest|import\s*\(|importScripts\s*\(|serviceWorker\b)", data.decode("utf-8")):
                raise BuildError("Script contains a network/module dependency: " + relative)
            if suffix == ".svg":
                text = data.decode("utf-8")
                for ref in re.findall(r"(?:href|xlink:href)\s*=\s*['\"]([^'\"]+)", text):
                    if not ref.startswith(("#", "data:")):
                        raise BuildError("SVG must have no external resources: " + relative)
                if re.search(r"@import|url\(\s*['\"]?(?!#|data:)[a-zA-Z./]", text):
                    raise BuildError("SVG contains an external style resource: " + relative)
            record = {"mime": mime, "base64": base64.b64encode(data).decode("ascii")}
            key_data = data
        asset_id = hashlib.sha256(mime.encode("ascii") + b"\0" + key_data).hexdigest()
        self.assets.setdefault(asset_id, record)
        self.asset_paths[relative] = asset_id
        self.loading.remove(relative)
        return asset_id

    def compile(self):
        index = 0
        while index < len(self.pending):
            relative = self.pending[index]
            index += 1
            if relative in self.pages:
                continue
            data = self.read(relative).decode("utf-8")
            slug = self.root.parent.name
            event = next(e for e in discover(self.root.parents[2]) if e["slug"] == slug and e["year"] == self.root.name)
            data = portable_navigation(normalise_page(self.root.parents[2], event, relative, data))
            if relative == "index.html":
                data = data.replace('href="../../../shared/reader-navigation.css"', 'href="web/navigation.css"')
            if TOKEN in data:
                raise BuildError("Source contains a reserved distribution marker")
            parser = PageCompiler(self, relative)
            parser.feed(data)
            parser.close()
            output = "".join(parser.out)
            script = "<script>" + self.bridge + "</script>"
            output = re.sub(r"</body\s*>", lambda _: script + "</body>", output, count=1, flags=re.I) if re.search(r"</body\s*>", output, re.I) else output + script
            self.pages[relative] = {"html": output, "title": parser.title.strip() or relative}
        if self.include_pdfs:
            for kind, label, _ in DOCUMENTS:
                name = editions(self.root.parents[2], event).get(kind, {}).get("pdf")
                if name and (self.root / name).is_file():
                    self.pdfs.append({"name": label, "asset": self.asset(name), "filename": Path(name).name})
        # Stable order and no timestamps, UUIDs, file locations, or compressed-stream metadata.
        return {
            "format": 1, "entry": "web/index.html",
            "pages": dict(sorted(self.pages.items())),
            "assets": dict(sorted(self.assets.items())),
            "pdfs": self.pdfs, "sources": dict(sorted(self.sources.items())),
        }


class PageCompiler(HTMLParser):
    def __init__(self, compiler, relative):
        super().__init__(convert_charrefs=False)
        self.compiler = compiler
        self.relative = relative
        self.out = []
        self.title = ""
        self.in_title = False
        self.in_style = False

    def tag(self, tag, attrs, closed=False):
        values = dict(attrs)
        if tag in {"base", "iframe", "object", "embed"}:
            raise BuildError("Unsupported embedded document element in " + self.relative + ": " + tag)
        if "srcset" in values:
            raise BuildError("Flatten responsive srcset assets before packaging: " + self.relative)
        if tag == "script" and values.get("type") == "module":
            raise BuildError("Classic scripts are required for offline packaging")
        for key in ("src", "poster"):
            if values.get(key):
                values[key] = self.compiler.resource(self.relative, values[key])
        if tag == "link" and "stylesheet" in values.get("rel", "").lower():
            values["href"] = self.compiler.resource(self.relative, values["href"])
        if "style" in values:
            values["style"] = self.compiler.css(values["style"], self.relative)
        if tag == "a" and values.get("href"):
            ref = values["href"]
            path, fragment = self.compiler.resolve(self.relative, ref)
            if path is None:
                if ref.startswith(("http:", "https:")):
                    values.update(target="_blank", rel="noopener noreferrer")
            elif Path(path).suffix.lower() == ".html":
                if path not in self.compiler.pending:
                    self.compiler.pending.append(path)
                values["data-so-page"] = path
                values["data-so-fragment"] = fragment
                # Keep native lesson hashes so the source's search code still works.
                values["href"] = "#" + fragment if path == self.relative else "#"
            elif Path(path).suffix.lower() == ".pdf" and not self.compiler.include_pdfs:
                values["href"] = "#"
                values["data-so-separate-pdf"] = ""
                values["title"] = "Printable PDF supplied separately"
            else:
                values["href"] = self.compiler.token(self.compiler.asset(path), fragment)
                values.update(target="_blank", rel="noopener")
        text = "<" + tag
        for key, value in values.items():
            text += " " + key + ("" if value is None else '="' + html.escape(value, quote=True) + '"')
        self.out.append(text + (" />" if closed else ">"))
        if tag == "title": self.in_title = True
        if tag == "style": self.in_style = True

    def handle_starttag(self, tag, attrs): self.tag(tag, attrs)
    def handle_startendtag(self, tag, attrs): self.tag(tag, attrs, True)
    def handle_endtag(self, tag):
        self.out.append("</" + tag + ">")
        if tag == "title": self.in_title = False
        if tag == "style": self.in_style = False
    def handle_data(self, data):
        if self.in_title: self.title += data
        self.out.append(self.compiler.css(data, self.relative) if self.in_style else data)
    def handle_entityref(self, name):
        self.out.append("&" + name + ";")
        if self.in_title: self.title += html.unescape("&" + name + ";")
    def handle_charref(self, name):
        self.out.append("&#" + name + ";")
        if self.in_title: self.title += html.unescape("&#" + name + ";")
    def handle_comment(self, text): self.out.append("<!--" + text + "-->")
    def handle_decl(self, decl): self.out.append("<!" + decl + ">")
    def handle_pi(self, data): self.out.append("<?" + data + ">")


LICENSE_FILES = ("LICENSE.md", "NOTICE", "THIRD_PARTY_NOTICES.txt", "LICENSES/Apache-2.0.txt", "LICENSES/CC-BY-4.0.txt")

def license_files(project_root):
    root = Path(project_root)
    return {name: (root / name).read_bytes() for name in LICENSE_FILES}

def licensing_section(project_root):
    parts = ['<details class="licensing"><summary>Licensing and exceptions</summary>']
    for name, data in license_files(project_root).items():
        parts.append('<h2>' + html.escape(name) + '</h2><pre style="white-space:pre-wrap;overflow-wrap:anywhere">' + html.escape(data.decode('utf-8')) + '</pre>')
    return ''.join(parts) + '</details>'

def build(project_root, event, year="2027", include_pdfs=False):
    record = next((e for e in discover(project_root) if e["slug"] == event and e["year"] == str(year)), None)
    if record is None:
        raise BuildError("Unknown event or year")
    compiler = Compiler(Path(project_root) / "events" / event / str(year), include_pdfs)
    bundle = compiler.compile()
    entry = bundle["pages"][bundle["entry"]]
    entry["html"] = entry["html"].replace("</body>", licensing_section(project_root) + "</body>", 1)
    bundle["title"] = str(year) + " " + record["name"]
    title = html.escape(bundle["title"])
    payload = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    support = Path(__file__).parent / "standalone"
    shell = (support / "shell.html").read_text()
    host = (support / "reader.js").read_text()
    output = shell.replace("__TITLE__", title).replace("__DISPLAY_TITLE__", html.escape(record["name"])).replace("__PAYLOAD__", payload).replace("__HOST_SCRIPT__", host).encode("utf-8")
    stats = {"event": event, "html_pages": len(bundle["pages"]), "unique_embedded_assets": len(bundle["assets"]),
             "source_files": len(bundle["sources"]), "source_bytes": sum(item["bytes"] for item in bundle["sources"].values()),
             "included_pdfs": len(bundle["pdfs"]), "output_bytes": len(output), "sha256": hashlib.sha256(output).hexdigest()}
    return output, stats, bundle


ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event", help="Event slug from manifests/events.json")
    parser.add_argument("--year", default="2027", help="Event year (default: 2027)")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path, help="New HTML path (default: build/standalone); existing files are never overwritten")
    destination.add_argument("--stdout", action="store_true", help="Write only HTML bytes to standard output")
    parser.add_argument("--include-pdfs", action="store_true", help="Embed registry-declared print PDFs too (excluded by default)")
    parser.add_argument("--project-root", type=Path, default=ROOT/"build/candidates",
                        help="Generated candidate tree (default: build/candidates)")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    try:
        if not args.stdout and args.output is None:
            # Never turn raw CLI selectors into an unchecked output path.
            if not re.fullmatch(r"[a-z0-9-]+", args.event) or not re.fullmatch(r"[0-9]{4}", args.year):
                raise BuildError("Expected a registered event slug and four-digit year")
            args.output = ROOT/"build"/"standalone"/f"{args.event}-{args.year}-standalone.html"
            args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output:
            target = args.output.expanduser().resolve()
            if target.is_relative_to(ROOT) and not target.is_relative_to(ROOT/"build"):
                raise BuildError("Choose an output under build/ or outside the source project")
            try:
                target.relative_to(root)
                if not target.name.endswith("-standalone.html"):
                    raise BuildError("Inside the input tree, use a *-standalone.html name or choose a separate output path")
            except ValueError as error:
                if isinstance(error, BuildError): raise
            if target.exists():
                raise BuildError("Output already exists; choose a new path: " + str(target))
            if not target.parent.is_dir():
                raise BuildError("Output parent directory does not exist: " + str(target.parent))
        output, stats, _ = build(root, args.event, args.year, args.include_pdfs)
        if args.stdout:
            sys.stdout.buffer.write(output)
        else:
            # A private sibling and no-clobber link make installation atomic.
            name = None
            try:
                with tempfile.NamedTemporaryFile(prefix="." + target.name + ".", dir=target.parent, delete=False) as stream:
                    name = Path(stream.name)
                    stream.write(output)
                os.link(name, target)
            finally:
                if name is not None: name.unlink(missing_ok=True)
        print(json.dumps(stats, sort_keys=True), file=sys.stderr)
    except (BuildError, OSError, UnicodeError) as error:
        parser.exit(1, "Standalone build failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()

