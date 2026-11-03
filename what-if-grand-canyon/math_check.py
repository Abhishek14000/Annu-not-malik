"""Recompute every number used in the narration (see MATH.md)."""
V = 4.17e12          # m3, NPS
PEE = 0.25e-3        # m3 per pee
POP = 8.3e9
DAILY = 1.5e-3       # m3 per person per day
RIVER = 8.23e6 * 1233.48 / (365.25 * 86400)  # m3/s from 8.23 million acre-feet a year
EVAP, AREA = 1.896, 4931e6                    # m/yr (USGS Lake Mead), m2 (NPS park area)
five_k = 5000 * PEE
print(f"5,000 pees: {five_k*1000:,.0f} L = {five_k/0.2:.2f} bathtubs; fraction {five_k/V:.2e}; river clears it in {five_k/RIVER*1000:.1f} ms")
world = POP * PEE
print(f"everyone once: {world:,.0f} m3 = {world/2500:,.0f} pools = {world/V*100:.6f}% of canyon")
print(f"people to fill: {V/PEE:.3e} = {V/PEE/POP:,.0f} Earths")
d = POP * DAILY
print(f"humanity per day: {d:,.0f} m3; years to fill (dammed, no losses): {V/d/365.25:,.0f}")
print(f"evaporation at full: {EVAP*AREA/365.25:,.0f} m3/day; lake stalls at {d*365.25/EVAP/1e6:,.0f} km2 = {d*365.25/EVAP/AREA:.0%} of footprint")
