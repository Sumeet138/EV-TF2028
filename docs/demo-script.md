# Demo script: three minutes, Maharashtra

Geography: Maharashtra, with Pune (best-served large district) against Amravati (worst-ranked district in India). Figures are from `data/processed/`. If a number on screen differs after a data refresh, say the on-screen number.

Say "modelled" every time you read an EV count or a gap score. Say "measured" for stations, VAHAN state totals and Census counts.

## 0:00 to 0:20, the problem

Screen: national map, `#/map`.

"Public chargers in India sit in many operator apps. We joined five public lists into one map: 31,259 stations after removing duplicates. The official count is 52,718 (Lok Sabha, July 2026), so we see about 59%, and the BEE list in it is from December 2024 and may hold closed stations. That share stays on screen, per state, because a gap here is a prompt to check, not proof that no charger exists."

## 0:20 to 0:50, the data join

Screen: toggle chargers, then the district layer.

"VAHAN gives EV registrations per state. Nationally that is 10.8 million EVs, against 1.00 crore in Parliament's July 2026 figure; the gap is timing plus a 2 to 3% residual. We split each state's count across its districts using RTO-level registrations where an RTO matches a district, and households, income proxy and night lights elsewhere. An RTO is not a district, so that is a caveat too. Those district numbers are modelled and labelled that way everywhere."

## 0:50 to 1:20, the state

Screen: select Maharashtra (`?s=Maharashtra`), open `#/scorecard`.

"Maharashtra has 1,218,821 EVs, measured, and 4,887 listed stations. Its state gap score is 61.3, band 4 out of 5. A state average hides the districts."

## 1:20 to 2:00, two districts

Screen: scorecard, select Pune, then Amravati.

"Pune has 1,802 stations, second only to Bangalore, and about 118 modelled EVs per adjusted charger. Its gap score is 50.6, band 3. Even so, only about 28% of its area is within 3 km of a charger, the urban norm in the Ministry of Power guidelines (2022, amended 2023).

Amravati has 35 stations and about 755 modelled EVs per adjusted charger. On average you are 15.4 km from the nearest charger, and 3.3% of the area meets the 3 km norm. Gap score 89.4, band 5, the worst of all 735 districts. Read the drivers shown on the panel, then point at the confidence label: high, because the census match is exact and its EV count rests on matched RTOs."

## 2:00 to 2:35, what to build

Screen: `#/planner`, district Amravati, year 2030.

"The planner turns the gap into a number. Pick a year and a scenario. It shows required chargers by type and how many to add. Every input is editable: fleet mix, public charging share, utilisation. Change one and the result updates. The assumptions list sits on the method page, each marked measured, norm, modelled or assumed."

Read the 2030 chargers-to-add figure for Amravati from the screen with its low to high range (base 2,759 today, for Pune 13,669). Never quote the base without the range. Say that utilisation of 15% is a 2035 target, ramping from 4.5%.

Screen: sites. "Candidate sites are placed to cover EVs that no listed charger reaches. They come with the nearest substation distance, because the grid decides what is buildable."

## 2:35 to 3:00, corridors and close

Screen: `#/corridors`, pick NH 27.

"Highways are measured against the 25 km spacing norm, on the real MoRTH and GatiShakti road geometry from June 2022. Lengths are lower bounds because the file has holes. NH 27 needs 30 more stations by that rule, the largest figure in the set; across 18 corridors the total is 219."

Close: "Next step is to replace what is weakest: agreed operator feeds, the live official charger list, and a validated RTO to district list. The method is the same, only the inputs get better."

## Do not say

- "There are no chargers in Amravati." We listed 35; the official list may hold more.
- "2025 guidelines." The norms are the 2022 guidelines amended in 2023; a 2024 update may be stricter.
- Any EV or gap number without the word modelled.
- Anything about the forecast beyond what the planner shows on screen.
