# Identification photo selection · 18 November 2026

Follow [the shared selection process](../../../../docs/image-selection.md). The target is the 23 identification categories in the event metadata, not a species checklist invented from photographs.

## What was reviewed

Reviewed actual pixels for all 47 existing photographs (23 first views and 24 alternatives). Fish review covered 22 existing photographs and 7 downloaded alternatives; other invertebrates covered 20 existing photographs and 5 alternatives. Coral/fan/algae review covered the remaining 5 existing photographs and 6 alternatives. The fish and invertebrate passes each used 8 targeted search queries. These are inspected-photo counts, not counts of every search thumbnail. Searches included Commons, NOAA collections, photographer/Flickr records, observation archives and FishBase; all imported images have individual Commons records, with upstream attribution where supplied. This was a focused comparative search, not proof that no better photograph exists.

Earlier provenance records documented selected sources and a visual check but not a comparative shortlist or search breadth. Do not retroactively claim exhaustive original curation.

## Decisions by category

| Category | Decision and teaching value |
| --- | --- |
| Butterflyfish | Retain contrasting patterns and side profiles; eye bands and body form remain visible. |
| Parrotfish | Retain exposed beak and contrasting phase. Another colorful side view would duplicate the job. |
| Snapper | Promote existing bluestripe whole fish; school becomes a harder recognition view. Retain species/color variants. |
| Humpback grouper | Retain adult/juvenile variation; elevated back and spots visible. |
| Bumphead parrotfish | Retain head and whole-body views; exposed beak is important beside wrasse lips. |
| Humphead wrasse | Retain adult/juvenile pair. A sharp head close-up is a useful later comparison, not necessary for another general portrait. |
| Nassau grouper | Retain bars/head and natural-habitat variation. Do not select NOAA-hosted photographs without resolving individual reuse rights. |
| Large grouper | Promote existing broadside giant grouper; obscured dusky grouper becomes habitat challenge. Neither establishes measured length. |
| Moray eel | Replace primary with Delso coiled geometric moray on sand, exposing continuous dorsal fin and tapered tail; retain contrasting whitemouth head detail. |
| Sweetlips | Replace dark diver frame with Albert Kok's clear adult body and fleshy lips. Retain contrasting juvenile; do not claim the pair is the same species. |
| Banded coral shrimp | Retain pair; newly inspected quality-badged alternative has soft foreground claw and unnecessary surroundings. |
| Spiny lobster | Replace both views with complementary CSIRO body detail and Delso full-antenna habitat view. No selected single photograph gives equally clear body and entire antennae. |
| Pencil urchin | Replace extreme close-up alternative with Nick Hobgood's complete upper view; retain underside primary. Stout spine bases contrast with Diadema. |
| Long-spined urchin | Promote isolated Diadema; explicitly mixed-species group becomes recognition challenge. |
| Crown of thorns | Promote clearer isolated animal; retain reef view. Historical A. planci labels may denote a species complex. |
| Sea cucumber | Retain smooth and spiky forms; useful texture/shape diversity. |
| Demosponge | Retain tubes and barrel. Encrusting forms remain a possible later addition. |
| Triton | Retain living animal; replace museum alternative with MerlinCharon complete apertural/dorsal shell pair, without answer labels. |
| Giant clam | Retain living mantle variation. Six-view H. Zell shell plate is a useful future shell-anatomy figure but too panoramic for the current single-photo card; not added solely to inflate coverage. |
| Flamingo tongue | Retain patterned living mantle and plain empty shell: an important identification trap. |
| Sea fan | Add NOAA dark branching mesh view to purple colony; same species, different visibility/lighting. Reject softer cyan Molasses Reef view. |
| Stony coral | Add NOAA brain-coral ridges/valleys to branching examples. Reject spawning-particle and strongly blue-lit alternatives for this identification job. |
| Fleshy algae | Add red Gracilaria tuft to brown Dictyota and green Caulerpa. Genus-level source only; do not substitute calcified algae for fleshy algae. |

## New source and comparison evidence

Exact selected URLs, creators, licenses, original dimensions and archive hashes are in the canonical `manifests/rights-inventory.json` and technical shared raster manifest; teaching records now reference source IDs. New masters retain full native resolution, reversibly archived from original JPEGs; delivered images are independently resized/re-encoded. Captions state useful visible evidence rather than promising exact species recognition.

- Sweetlips: [selected Albert Kok](https://commons.wikimedia.org/wiki/File:Plectorhynchus.jpg), CC BY-SA 3.0. Current description says P. chaetodonoides; original upload says P. gaterinus. Group is clear, so omit species. Compared Hectonichus's overlapping group and Derek Keats's softer/darker broadside. A Diego Delso DD08 image labeled sweetlips showed incompatible puffer-like morphology and was rejected despite its quality badge; do not propagate its label without expert confirmation.
- Pencil urchin: [Nick Hobgood](https://commons.wikimedia.org/wiki/File:Eucidaris_tribuloides_(Slate-pencil_Urchin).jpg), own work, CC BY-SA 3.0, complete body/spine structure.
- Sea fan: [Maya Walton/NOAA](https://commons.wikimedia.org/wiki/File:Sea_fan_Gorgonia_ventalina.jpg), individual federal-work declaration and [original NOAA gallery](https://sanctuaries.noaa.gov/news/aug14/gallery.html). [Molasses Reef alternative](https://commons.wikimedia.org/wiki/File:Gorgonia_flabellum,_Molasses_Reef.jpg) has less useful focus/lighting. Reefguide photographs were not imported: copyright notice is not a reusable license.
- Brain coral: [Emma Hickerson/NOAA](https://commons.wikimedia.org/wiki/File:FGBNMS_-_symmetrical_brain_coral_closeup_(27369203594).jpg), individual federal-work declaration and reviewed NOAA Flickr provenance. Compared [spawning](https://commons.wikimedia.org/wiki/File:FGBNMS_Brain_Coral_(48779407602).jpg) and [ROV close-up](https://commons.wikimedia.org/wiki/File:Brain_Coral_(16434980063).jpg).
- Red alga: [Rickard Zerpe](https://commons.wikimedia.org/wiki/File:Red_algae_(Gracilaria_sp.)_(48737220543).jpg), CC BY 2.0, reviewed Flickr source; visible separated tuft and fleshy branches, source says Gracilaria sp.
- Deferred [H. Zell clam shell plate](https://commons.wikimedia.org/wiki/File:Tridacna_gigas_02.jpg), CC BY-SA 3.0: one juvenile left valve, six views, not six living clams. A dedicated anatomy panel would be better than shrinking it into the existing photo slot.

## Limits and next useful checks

This does not guarantee an unseen competition image will be recognized. No student learning trial or physical-print test was performed. The focused follow-up below addressed the three priority gaps; the lobster pair still needs both views because the full-antenna habitat photograph has a dark, partly hidden body. Current species examples do not exhaust broad categories. Generated cover art is motivational illustration, never identification evidence. Recheck taxonomy or rights if an upstream record changes.

## Verification of this pass

The Docker candidate build succeeded; all 66 repository tests passed against the generated candidate tree. Replaced the stale standalone-package test's fixed two-PDF assumption with exact registry-declared filename/count checks. Verified original JPEG reconstruction byte-for-byte for all five new source masters. The collection now has 23 primary and 27 supplemental photographs. Reviewed rendered study-guide pages 17–55, with an independent review of pages 17–32; corrected the stale juvenile-sweetlips caption and rechecked its final page and credit. No clipping was found; existing atlas whitespace remains. Grayscale previews retain fan mesh, coral ridges, lips and stout spines; the red alga has weaker grayscale separation. Browser interaction, physical printing and student learning trials were not performed in this pass.

## Focused follow-up: closing the three priority gaps

Inspected 35 additional lobster photographs and one illustration, 11 additional moray photographs and four additional triton shell photographs. These are downloaded/pixel-viewed candidates, not search-result counts; some lobster candidates were first screened using official previews before downloading selected originals. Searches spanned Commons own-work records, NOAA, Flickr, iNaturalist observations, CSIRO, an open taxonomic paper, Naturalis, Museums Victoria and Smithsonian. Not every searched collection yielded a usable/downloadable candidate. Full originals of all four replacements were obtained; none uses an enlarged thumbnail.

- **Moray:** selected [Diego Delso geometric moray DD185](https://commons.wikimedia.org/wiki/File:Morena_pimienta_(Gymnothorax_griseus),_parque_nacional_Ras_Muhammad,_Egipto,_2022-03-27,_DD_185.jpg), CC BY-SA 4.0, 2450×1633. The entire coiled body and raised dorsal fin separate from sand. Compared LASZLO ILYES's [Echidna nebulosa 1](https://commons.wikimedia.org/wiki/File:Echidna_nebulosa_1.jpg), a good whole-body runner-up whose reef texture obscures the fin; full-view green morays at Oceanografic, Gymnothorax unicolor/castaneus/moluccensis/griseus/javanicus and two iNaturalist snowflake morays had cropped, hidden or flattened fins/bodies. NOAA's sharp head view did not solve the body gap. Retain the whitemouth head view for contrast; corrected its former reference to the green primary.
- **Triton:** selected [MerlinCharon Charonia tritonis a1](https://commons.wikimedia.org/wiki/File:Charonia_tritonis_a1.jpg), creator public-domain dedication, 3971×3309. Complete apertural and dorsal views, clear spire/opening/striped lip, no answer labels. Compared AntanO's softer, saturated one-side image and Naturalis 192627/192634 oblique/overlapping catalog plates, plus previously rejected 192630. Museums Victoria F83077 had usable CC BY rights but its image could not be inspected; Smithsonian candidate returned unavailable. Shell structure cross-checked against the [FAO identification guide, p.541](https://www.vliz.be/imisdocs/publications/391449.pdf). Source photographer warmed the original colors; do not use it as calibrated color evidence.
- **Lobster:** selected [Robert Kerton/CSIRO ScienceImage 2518](https://commons.wikimedia.org/wiki/File:CSIRO_ScienceImage_2518_Ornate_Lobster.jpg), CC BY 3.0, 2657×1765, for exposed body, carapace, abdomen, legs and antenna bases; caption expressly says tips extend outside the frame. Pair with [Diego Delso Palinurus elephas DD03](https://commons.wikimedia.org/wiki/File:Langosta_común_(Palinurus_elephas),_Parque_natural_de_la_Arrábida,_Portugal,_2021-09-10,_DD_03.jpg), CC BY-SA 4.0, 6208×4139: both long antennae fit inside the image, but the body is dark/partly hidden. Both are Palinuridae examples, not the same species. Compared Douglas Whitaker's Panulirus argus deck photo, CSIRO 3341, NOAA/Claire Fackler, Assianir aquarium, six Flickr photos, numerous independently labeled iNaturalist photos (including four Caribbean examples), Panulirus guttatus aquarium views and an expert-identified [P. femoristriga specimen figure](https://pmc.ncbi.nlm.nih.gov/articles/PMC8885632/). All had cut/broken antennae, hidden body, distracting tank reflections or weaker detail. Sean Nash's natural sandy view and Florida Sea Grant's diagram were excluded for NC/ND restrictions, not silently relicensed. Neither selected frame alone is ideal; complementary detail/context views teach more than another clipped close-up.

The collection remains 23 primary and 27 supplemental photographs. The four replacement JPEG originals reconstruct byte-for-byte from their JPEG XL masters. Individual source-image licenses remain attached to images and derivatives; the project's CC BY text license does not override CC BY-SA photographs. No generated image was used as identification evidence.

Follow-up verification: Docker rebuilt all candidates and the 168-file Pages export successfully; all 66 tests passed against that final candidate tree. Rendered final study-guide pages 22–24 and 33 show the replacement photographs and captions without clipping. The dark lobster habitat view retains both antennae in frame but is intentionally a harder recognition example, not the sole anatomy view. An independent fish reviewer confirmed the moray's body/fin claims and source identification/license. No publication or commit was performed by this curation pass.

Independent review caught stale root rights-inventory records after asset replacement (including the earlier pencil-urchin alternative). Reconciled all 50 photo records with event provenance, checked every notice block and added one regression test for actual asset hashes plus creator/license/source/modification agreement. The repeatable process now explicitly includes the root rights inventory; passing rendering tests alone is not a rights-record check.

After that correction, the full Docker build/export succeeded again (168 files) and all 67 tests passed against the newly rebuilt candidate tree. A whole-inventory hash check found no mismatches among existing files.

## Provenance consolidation

Photo source/creator/license facts now live only in the canonical root rights inventory. Event teaching records refer to stable source IDs; PDF/web/practice credits and the public notices are generated. The earlier cross-inventory reconciliation above records the historical review, not an instruction to maintain duplicate inventories. See `docs/provenance.md`.
