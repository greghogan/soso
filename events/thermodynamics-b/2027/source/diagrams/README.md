# Thermodynamics diagrams

`generate.py` contains the editable drawing code for 14 reproducible SVGs. The shared guide builder runs it before generating either PDFs or web previews. It writes to the event's build directory, never to the source tree. The six SVGs under `assets/diagrams/` are the canonical artwork for manually finalized figures; the generator does not replace them. See `../diagram-provenance.json` for reviewed fixture hashes and scientific attribution.
