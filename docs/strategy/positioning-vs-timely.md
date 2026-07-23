# Positioning: Gittan vs. Timely

**Status:** draft · **Created:** 2026-07-23 · **Owner:** @mbjorke

> Working note, not doctrine. Timely is the closest analog to what Gittan does,
> which makes it the sharpest mirror for deciding what Gittan is *not*.

## TL;DR

Timely has already validated the market: people will pay to *stop* tracking time
manually and let software draft their hours from real activity. We don't need to
prove the need — we need to serve the slice Timely structurally can't: people who
refuse to upload their workday to someone else's cloud.

Treat Timely as **proof and benchmark, not destination.**

## Who Timely is

Timely (Memory AS) runs a "Memory" engine that passively captures activity and
**drafts** timesheets so the user confirms rather than logs from scratch. It's a
team-oriented SaaS: data lives in Timely's cloud, sold on a per-seat subscription,
and the economic buyer is often an agency or manager, not the individual.

## The contrast that matters

|                     | Timely                         | Gittan                             |
| ------------------- | ------------------------------ | ---------------------------------- |
| Where data lives    | Their cloud                    | The user's machine (local-first)   |
| Business model      | Per-seat SaaS                  | Local-first / open core            |
| Primary buyer       | Agencies, teams, managers      | The freelancer / solo consultant   |
| Core promise        | "We draft your hours"          | "We draft your hours — nothing leaves your machine" |

The single line Timely cannot say without cannibalizing its own cloud model:

> **Your activity data never leaves your computer.**

That is our wedge.

## What we take from them (benchmark)

- **The confirm-your-hours flow.** Their onboarding and "review draft → confirm"
  UX is a solved problem worth studying — it's the exact UX challenge Gittan faces
  next (activity → suggested hours → 30-second confirm → invoice).
- **Passive capture as the headline, manual logging as the fallback** — not the
  reverse.
- **Framing time-tracking as recovered revenue**, not admin overhead.

## What we deliberately reject

- **Cloud as the default.** Our privacy claim ("nothing leaves the machine") is a
  sales point only if it's documented and true — not a footnote.
- **Selling to the manager.** We serve the individual who does the billable work
  and hates tracking it. Different buyer, different product.
- **Building *for* Timely** (integration, subcontractor, acquisition bait). That
  couples our survival to a company whose core value (centralized cloud data)
  contradicts ours (local, decentralized). Aiming to be acquired is a hope, not a
  strategy. The way to become interesting to a Timely is to build the local,
  privacy-first product so well their own users ask for it — then the conversation
  comes to us.

## The wedge, stated plainly

> **"Timely for people who won't upload their day."**

Target the privacy-conscious tail of a market Timely has already proven exists:
the hourly-billing freelancer and small agency in the Nordics, where the
Briox/Fortnox invoicing integration is our concrete edge.

## Near-term implications

1. Make the privacy claim provable (documented data boundaries), not asserted.
2. Invest in the confirm-hours UX — that's where Timely is ahead and where our
   retention will live.
3. Success metric: someone other than the maintainer bills real hours through
   Gittan and says it saved them time and money.
