# Product adoption forces — why people decide to use a product

The citable taxonomy of adoption drivers (operator-requested 2026-08-30). Consumed at TWO points:
**spec time** — a market-facing spec's `Why this exists` / `## Personas` names WHICH forces (by id)
its primary persona feels, so the design rides a real force instead of an assumed one; and
**distribution time** — channel choice follows the force (a product bought on AF-23 trigger events
needs to be findable at the trigger moment (AF-24), not ambiently advertised; an AF-25 default play
needs a bundling partner, not SEO).

**The umbrella model (Jobs-to-be-Done "four forces"):** adoption happens when
**push of the current pain (AF-1..6) + pull of the new (AF-7..22) > anxiety about switching + habit
of the status quo (AF-17, AF-10)**. Most products fail on the right side of that inequality — the
switch felt risky and the old way was tolerable — not on missing features. The sharpest spec
question is therefore: *whose pain, and why is TODAY the day they switch (which AF-23 trigger)?*

## Pain / function (push forces)

| id | Force | The decision it drives |
|---|---|---|
| AF-1 | Removes an acute pain | kills a recurring cost in time, money, errors, or stress — the "painkiller" |
| AF-2 | Better at an existing job | faster/cheaper/better tool for a job they already do |
| AF-3 | Capability unlock | enables something previously impossible, not an optimization |
| AF-4 | Automates drudgery | they could do it manually, but resent it |
| AF-5 | Risk reduction / insurance | backup, security, monitoring — bought for the disaster that hopefully never comes |
| AF-6 | Forced adoption | regulation, employer mandate, platform requirement, a client's format — the environment decided |

## Economics

| id | Force | The decision it drives |
|---|---|---|
| AF-7 | Makes them money | directly generates revenue or leads — the easiest B2B sale |
| AF-8 | Cheaper than the incumbent | same job, lower price |
| AF-9 | Free | zero-cost entry beats a better paid rival for many jobs |
| AF-10 | Switching-cost avoidance | chosen for compatibility with what they have, not for being best |

## Emotion / identity

| id | Force | The decision it drives |
|---|---|---|
| AF-11 | Status / signaling | the product says something about them to others |
| AF-12 | Identity fit | "I'm the kind of person who uses this" — privacy tools, open source, luxury, minimalism |
| AF-13 | Fear relief / FOMO | anxiety about missing out, falling behind, being exposed |
| AF-14 | Pleasure / entertainment | using it feels good; no job beyond that |
| AF-15 | Curiosity / novelty | trying the new thing is the point |
| AF-16 | Progress / mastery | streaks, levels, skill growth — the feeling of advancing |
| AF-17 | Comfort / habit | familiar beats better; they've always used it |

## Social gravity

| id | Force | The decision it drives |
|---|---|---|
| AF-18 | Network effects | the people or data they need are already inside |
| AF-19 | Social proof | reviews, ratings, "everyone I respect uses it", case studies |
| AF-20 | Trusted recommendation | word of mouth, an authority, an influencer |
| AF-21 | Team / peer imposition | the group chose it; the individual adopts to collaborate |
| AF-22 | Belonging | the community around the product is the actual draw |

## Situation / distribution (the timing forces — channel choice starts HERE)

| id | Force | The decision it drives |
|---|---|---|
| AF-23 | Trigger event | something broke, job change, growth, an incident — yesterday's tolerable pain became urgent |
| AF-24 | Findable at the moment of need | SEO, app-store search, shelf placement — often the decider between equals |
| AF-25 | The default | pre-installed, bundled, the platform's built-in — the most underrated force on this list |
| AF-26 | Only option | monopoly, lock-in, or a niche nobody else serves |

## Experience deciders (what wins the comparison once they're choosing)

| id | Force | The decision it drives |
|---|---|---|
| AF-27 | Lowest friction to first value | easiest onboarding, no credit card, works in 2 minutes |
| AF-28 | Speed and reliability | simply faster, and doesn't break |
| AF-29 | Design / aesthetics | pleasant to look at and touch |
| AF-30 | Stack fit | integrations, import/export, data portability |
| AF-31 | Trust posture | brand reputation, privacy/security stance, "will they exist in 3 years", auditability |
| AF-32 | Support and care | humans answer when it breaks |

## Cross-cutting truths

- **User ≠ payer ≠ decider** — often three different people (B2B especially). The personas
  contract's payer/receiver enumeration exists for exactly this: name which force acts on WHICH of
  the three.
- **The blocking side is usually anxiety + habit** (AF-17 + switching anxiety), not a missing
  feature — the counter-moves are AF-27 (friction), AF-30 (fits their stack, no rip-and-replace),
  AF-31 (trust), and AF-9 (free entry).
- **Forces compose per persona, not per product** — the same product can ride AF-7 for the buyer,
  AF-4 for the daily user, and AF-21 for the rest of the team. A spec that names one force for
  "the user" has usually collapsed three personas into one.

## How to cite (spec + rivals + release)

- **Spec time** (`/fabrik-spec` Phase 5): the `Why this exists` section of a market-facing spec
  names the primary persona's forces by id — e.g. *"rides AF-1 (repeated translation-loss pain)
  triggered by AF-23 (the volume-prune incident); blocked mainly by AF-17"*. Internal/infra specs
  cite forces only when a real adoption question exists (an internal tool still fights AF-17).
- **Rivals time** (`/fabrik-rivals`): MATCH/BEAT rows can name the force a competitor rides —
  beating an AF-25 default needs a different weapon than beating an AF-2 better-tool.
- **Distribution time**: pick channels FROM the timing forces — AF-23/24 → search + the places the
  trigger surfaces; AF-25 → bundling/partnerships; AF-18..22 → community + referral loops;
  AF-9/27 → free tier + instant onboarding as the channel itself.
