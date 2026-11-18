# Compact teaching diagrams

The Python source defines 14 original teaching figures, including synchronous
rotation. The study-guide build creates vector PDFs, vector SVGs with accessible
titles and descriptions, a lesson-to-figure manifest, and a structural QA report
under the event build directory. The build uses ReportLab, PyMuPDF, and the
DejaVu Sans fonts from the SOSO Docker image. There are no checked-in previews.

## Placement

Native width is **240 pt**. Place PDFs at **240 pt or wider** to preserve 9 pt minimum labels. On the web, a 240 pt figure is 320 CSS px; use a width of at least 320 CSS px where possible, or provide an enlarge control on narrow screens. Maintain intrinsic aspect ratio. Keep each manifest caption with its figure: several figures are intentionally qualitative or schematic rather than quantitative records.

PDFs contain no raster images. Do not substitute the PNG preview into the print pipeline when the vector PDF is available.

## Scientific conventions

- Hierarchy shows center-to-center distance definitions but not scaled geometry.
- Diameter dots use a true logarithmic horizontal axis; dot size does not encode diameter.
- Phase topology includes the negative-slope ordinary-ice melting boundary, not high-pressure phases or a fabricated numeric scale.
- Escape distributions are qualitative; nonthermal escape is excluded.
- Ocean columns explicitly distinguish Europa's expected contact from alternative Ganymede models.
- Bennu is a shape sketch with illustrative boulders, not a surface map or a present-day ocean model.
- Transit depth uses the uniform-star approximation; the two curves have the same vertical scale.
- Radial-velocity examples hold stellar mass, period, and eccentricity fixed and assume planet mass is small compared with stellar mass.
- Radar depth uses the subsurface echo delay relative to the surface echo, excluding the spacecraft-to-surface path.

The main lesson text remains authoritative for context and qualifications. These figures do not establish official event-rule requirements.

## Verification

The generator checks minimum label size, extracted text bounds, and that no
raster artwork is embedded in the vector PDFs. Inspect modified figures in the
PDF and web readers; structural checks cannot approve layout.
