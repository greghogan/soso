# Sources and credits

## One record per work

`manifests/rights-inventory.json` is the authoritative image provenance/rights inventory. Each third-party photograph has a stable `id`, current master `path` and `sha256`, source title, creator, source and license URLs, modifications, original download information and review evidence. Unknown rights remain unknown: do not infer a license from a scientific citation, host, or generated-image label.

Atlas and supplemental teaching data refer to `source_id`; they contain captions, alt text and teaching choices, not copied creators or licenses. `shared/provenance.py` resolves those references for PDF, web and practice credits, and fails if a reference points at the wrong file. Keep the source ID when replacing a file serving the same role, but replace all of that record's source facts and hash together.

`manifests/raster-masters.json` is the technical archive-integrity record (reconstruction/hash/encoding), not a second rights inventory. Generated-art origin notes and selection-review notes remain evidence linked from the inventory; they are not alternative licenses.

## Generated listings

Run `python3 shared/provenance.py` after changing rights records. This generates `THIRD_PARTY_NOTICES.txt` from the inventory and the preserved upstream font terms in `LICENSES/third-party-preamble.txt`. Do not edit the generated listing. `--check` detects a stale listing; the container build regenerates it in its disposable staging tree.

Every independent PDF/web guide retains source credits, and practice feedback retains photograph attribution. The public notices retain title, creator, original/source links, individual license and changes. Project CC BY terms do not replace third-party licenses; ShareAlike requirements remain attached to applicable photographs/derivatives.

## Text and scientific citations

Keep one entry per work in the event's existing source registry, referenced by stable IDs from lesson `sources`. This already generates that guide's reader-facing references. Record title, author/organization when known, URL/DOI, version/publication date and access date where useful. Use `locator` for a page, section, figure or table; use `note` for the specific fact supported or uncertainty. The shared study/build renderer displays these optional details. Optional `quotation` records exact reproduced wording and must include `locator` and `rights_basis`; do not confuse a paraphrase with a quotation. Citations establish evidence, not permission to reproduce text or images.

Do not invent absent bibliographic data or add a decorative citation unrelated to the claim. The official rules stay private/ignored; cite their edition and page without publishing the manual. Common facts need not be cited sentence by sentence, but claims a student needs to verify should have a nearby source reference. Preserve existing lesson IDs and source IDs when refining records.

## Review

Check master hashes and referenced IDs, run `./test.sh`, build a separate candidate, and inspect revised credit/reference pages and practice feedback. A metadata-only edit can change PDF pagination. Check citations and licenses against the actual source, not just the search snippet. Follow `image-selection.md` for candidate selection. A successful build is not a legal opinion or proof that the chosen examples improve learning.
