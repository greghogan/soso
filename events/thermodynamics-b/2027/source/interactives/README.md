# Offline interactive sources

Build a preview with `./scripts/build_web.py thermodynamics-b --year 2027`. Open `web/interactives/geometry.html` or `web/interactives/heat-flow.html` within the generated event directory. The checked-in HTML templates are build inputs, not standalone pages.
Preserve the event directory layout when copying. All HTML, CSS, classic JavaScript and SVG are local; there are no imports, fetch calls, remote assets, analytics, or saved personal data. Open either HTML file directly; a server is not intended to be required. Native details reveal explanations. Range controls support keyboard and touch. Reset restores the example. Print styles remove controls; static SVG fallbacks are also supplied for a PDF renderer or JavaScript-disabled browser.

## Rules and source boundary

Geometry was checked against the supplied 2027 Division B Rules Manual, printed pages B56–B58 (PDF pages 61–63), including the B57 apparatus diagram. See `../../research/verified-rule-schema.json` for source locators. This is an original diagram, not a reproduction of that page. Check current tournament clarifications before building.

Blue dashed geometry: rule envelope/datums. Teal geometry: a proposed open reflector, not an official recommended design. Bulb/fixture shape, example stand, water fill height, cup bottom width and support geometry are schematic. Overall dimensions include the cup height and 1 cm base but omit fastener and panel thickness; allow margin. Cup dimensions in the rules are approximate. Width clearance alone does not establish grip clearance, thermal safety, rigidity or legality. Lamp gap is a geometric distance, not a required or safe thermal clearance. Panel angle is a design choice; the model does not trace rays or predict captured power.

## Model boundary

`model.js` is the original deterministic source, usable as a classic browser script or CommonJS module. The model uses 100 mL water approximately 0.100 kg, water heat capacity 418 J/K, and one shared temperature for water/cup/device. Absorbed power P, loss coefficient UA and extra heat capacity Cextra are explicitly hypothetical, not measured or official. For C = 418 + Cextra, it solves C dT/dt = P - UA(T-Ta), with the zero-loss limit handled separately. It omits evaporation, temperature-dependent properties, separate thermal nodes, changing illumination and transfer/measurement delay. Effective absorbed power is not bulb electrical power. No inverse-square point-source claim is made for an extended lamp with reflector. Real builds require measured repeated trials and safety review. No slider position is a performance recommendation.

## Reproduce tests and static assets

From repository root:

    node events/thermodynamics-b/2027/source/interactives/test-models.cjs

The script checks the three SVG fallbacks and writes `build/interactive-qa/thermodynamics-b/2027/model-tests.json` at the repository root. Tests cover allowed level/height combinations, extremes, clearance flags, finite SVGs, analytic energy balance, sensible parameter trends, invalid domains and external dependency guards. No packages need installing; the test runner uses Node and Python 3 standard-library ElementTree for strict SVG XML parsing (the browser guide itself needs neither).

## Verification 2026-10-30

4,239 checks passed, including strict XML parsing of 1,083 SVG documents (all sampled geometry/chart combinations and the three static files). A duplicate stroke-width attribute found by independent QA was corrected in the generator; the XML regression rejects this class of error. Official page images and static SVG raster renders visually inspected. Managed browser preview verified national-height selection, oversized-device warning, narrow-opening warning, separate-cup toggle, model parameter changes, saved comparison and reset. Controls exposed accessible names/current values. Direct `file://` execution was blocked by the cloud browser's HTTP/S-only protocol policy; offline behavior has therefore been dependency-audited but not directly browser-executed. Mobile stacking is implemented (side and plan separated below 600 px); no actual mobile viewport test was available. These are verification limits, not claims of complete cross-browser or hardware validation.
