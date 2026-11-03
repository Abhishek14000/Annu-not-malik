# The maths: "What if 5,000 people peed into the Grand Canyon?"

All figures are rounded the way the narration says them. You can rerun them with `python3 math_check.py`.

## Inputs
| Quantity | Value used | Source | Notes |
|---|---|---|---|
| Grand Canyon volume | 4.17 × 10¹² m³ | National Park Service statistics page (archived 2008): 5.45 trillion cubic yards = 4.17 trillion m³ | Other estimates exist; the NPS figure is the standard one. |
| One pee | 0.25 L | Voiding-diary studies: median 220 mL (Journal of Urology 2009, 935 men); mean ≈ 244 mL (BMC Urology 2022) | Most studies are of men; 200–250 mL is typical. |
| Daily urine per person | 1.5 L | Common clinical reference range ≈ 0.8–2 L per day | Mid-range value. |
| World population | 8.3 billion | UN World Population Prospects 2024 projection for mid-2026 (8.30 bn); US Census Bureau: 8.2 bn | |
| Colorado River flow | ≈ 322 m³/s | Annual Glen Canyon Dam release of ≈ 8.23 million acre-feet, converted | Daily flows vary roughly 5,000–20,000 cfs. |
| Canyon depth | up to ≈ 1.8 km | Commonly cited maximum ≈ 6,000 ft (1,830–1,860 m) | Average ≈ 1 mile. |
| Evaporation | 1.9 m per year | USGS, Lake Mead 2010–2019 measured mean 6.22 ft (1,896 mm) | Lake Mead is the nearest large desert lake. |
| Lake surface if full | ≈ 4,900 km² | Grand Canyon National Park area, 4,931 km² (NPS) | A rough stand-in for the canyon's footprint. |
| Bathtub / Olympic pool | 200 L / 2,500 m³ | Typical sizes | |

## Results
| Line in the video | Calculation | Result |
|---|---|---|
| 5,000 pees ≈ 1,250 L ≈ six bathtubs | 5,000 × 0.25 L; ÷ 200 L | 1,250 L; 6.25 tubs |
| "three ten-trillionths" of the canyon | 1.25 m³ ÷ 4.17 × 10¹² m³ | 3.0 × 10⁻¹³ |
| River washes it away in ~4 ms | 1.25 m³ ÷ 322 m³/s | 0.0039 s |
| Everyone at once ≈ 2 million m³ ≈ 800 pools | 8.3 × 10⁹ × 0.25 L; ÷ 2,500 m³ | 2.08 × 10⁶ m³; 830 pools |
| 0.00005% of the canyon | 2.08 × 10⁶ ÷ 4.17 × 10¹² | 5.0 × 10⁻⁷ = 0.00005% |
| ≈ 17 quadrillion people, two million Earths | 4.17 × 10¹² m³ ÷ 0.25 L; ÷ 8.3 × 10⁹ | 1.67 × 10¹⁶; 2.0 × 10⁶ |
| Humanity ≈ 12 million m³ a day | 8.3 × 10⁹ × 1.5 L | 1.245 × 10⁷ m³/day |
| ≈ 900 years with both ends dammed | 4.17 × 10¹² ÷ 1.245 × 10⁷ per day | 334,900 days ≈ 917 years |
| The lake stalls at about half the canyon | Equilibrium: inflow 4.55 × 10⁹ m³/yr ÷ 1.9 m/yr | ≈ 2,400 km² ≈ 49% of 4,931 km² |

## Simplifications
- Ignores seepage into the rock, rain, and the river's own inflow (the dams "send only pee").
- The equilibrium treats evaporation as uniform over the lake surface and uses the park's area as the full-lake area. The point is the order of magnitude: at full size, evaporation (≈ 25.6 million m³/day) is about twice humanity's output (≈ 12.5 million m³/day).
- The droplet line is qualitative: liquid jets break into drops within a short distance (Plateau–Rayleigh instability). Millimetre-sized drops fall at a few metres per second, so a 1.8 km drop takes several minutes, and wind and evaporation in dry air would scatter much of it.
