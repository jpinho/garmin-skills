#!/usr/bin/env python3
"""Fetch Garmin's Personal API OpenAPI spec from the official Swagger docs page, and look up schemas.

  garmin_spec.py fetch OUT.json              # download and extract the spec (OpenAPI 3.0.1)
  garmin_spec.py show OUT.json SCHEMA [TEXT] # print a schema's properties (type, format, description),
                                             # optionally only those whose name or description contains TEXT

The docs page (https://developer.garmin.com/gc-developer-program/personal/swagger-docs/) is a Gatsby
site that embeds the spec in a JS bundle as JSON.parse('...'). This finds the bundle and decodes that
string literal. If Garmin restructures the site this breaks: open the page in a browser instead.
The spec is Garmin's documentation; keep the downloaded copy local rather than republishing it.
"""
import json
import re
import sys
import urllib.request

SITE = "https://developer.garmin.com"
PAGE = SITE + "/gc-developer-program/personal/swagger-docs/"
ESC = {"n": "\n", "t": "\t", "r": "\r", "'": "'", '"': '"', "\\": "\\", "/": "/"}


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "*/*"}), timeout=60) as r:
        return r.read().decode("utf-8")


def fetch():
    html = _get(PAGE)
    bundles = sorted(set(re.findall(r'/component---src-pages-gc-developer-program-personal-swagger-docs-js-[0-9a-f]+\.js', html)))
    if not bundles:
        sys.exit("Spec bundle not found on the docs page: the site layout has changed.")
    js = _get(SITE + bundles[0])
    marker = "JSON.parse('{\"openapi\":"
    i = js.find(marker)
    if i < 0:
        sys.exit("No embedded OpenAPI spec in the bundle: the site layout has changed.")
    i += len("JSON.parse('")
    out = []
    while js[i] != "'":
        c = js[i]
        if c == "\\":
            n = js[i + 1]
            if n == "u":
                out.append(chr(int(js[i + 2:i + 6], 16))); i += 6; continue
            if n == "x":
                out.append(chr(int(js[i + 2:i + 4], 16))); i += 4; continue
            out.append(ESC.get(n, n)); i += 2; continue
        out.append(c); i += 1
    return json.loads("".join(out))


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("fetch", "show"):
        sys.exit(__doc__)
    if sys.argv[1] == "fetch":
        spec = fetch()
        json.dump(spec, open(sys.argv[2], "w"), indent=1)
        print(f"{spec['info']['title']} {spec['info']['version']}: {len(spec['paths'])} paths, "
              f"{len(spec['components']['schemas'])} schemas -> {sys.argv[2]}")
        return
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    schemas = json.load(open(sys.argv[2]))["components"]["schemas"]
    name, text = sys.argv[3], (sys.argv[4].lower() if len(sys.argv) > 4 else "")
    if name not in schemas:
        sys.exit("Unknown schema. Close matches: " + ", ".join(s for s in schemas if name.lower() in s.lower())[:500])
    for prop, d in (schemas[name].get("properties") or {}).items():
        desc = d.get("description", "")
        if text and text not in prop.lower() and text not in desc.lower():
            continue
        kind = d.get("$ref", "").split("/")[-1] or d.get("format") or d.get("type", "")
        print(f"{prop:40} {kind:12} {desc}")


if __name__ == "__main__":
    main()
