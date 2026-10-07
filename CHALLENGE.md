# Take-Home Test: AI Engineer

## Context

Fundo gives revenue-based advances to small businesses. To make an offer, we read the business's last 90 days of bank transactions and turn them into a few numbers: monthly revenue, NSF and overdraft count, payments to other funders, and high-risk activity. Those numbers become features for a risk model and inputs to the offer.

Today, a keyword engine labels each transaction. It matches the description against keyword lists, one list per group, and precedence rules decide which group wins when several match. Each transaction is also marked as business or personal. A transaction becomes **revenue** only when it is a business credit and no excluding group matched.

The engine works, but it makes mistakes that keywords cannot fix:

- Bank descriptions are noisy: `ACH CREDIT 0423 SQ *JOES TACOS`, `ORIG CO NAME:SHOPIFY CO ENTRY DESCR:TRANSFER`.
- The same counterparty means different things. `SQUARE INC` deposits are revenue; `SQUARE CAPITAL` is a loan.
- A keyword that contains punctuation can silently never match.
- Some banks charge no NSF fees, so "zero NSFs" does not always mean a healthy account.

We do not want an LLM to relabel everything from scratch. We want an LLM **reviewer**: it reads the keyword labels and flags the ones it doubts, with a reason an underwriter can act on.

## The problem

Build the reviewer, show what its flags are worth to a funding decision, and say how it would go to production.

## Scope

**Expected effort: 6–8 hours. You are not expected to implement everything.**

Choose where you can show the most, and do that well. What you deliberately skipped, and why, is part of the answer.

The quality of your decisions matters more than the number of features.

---

## Data

**You get the data yourself.** We do not provide a dataset. How you find, understand and build it is part of the test.

- Use Plaid's transaction format. Read their documentation — fields, categories, sign conventions. Plaid Sandbox, synthetic generation, or both are fine.
- About 10 businesses, 90 days each, a couple of thousand transactions.
- Include the cases that matter to a funder. Which ones you think of tells us how well you understand the business.
- No real customer data.

### The keyword groups

Build a small keyword engine that labels your data with these 13 groups, plus a business/personal flag. A transaction is **revenue** when it is a business credit and no excluding group matched.

| Group | | Group |
|---|---|---|
| Not average monthly revenue | | Revenue verification |
| NSFs | | High risk — gambling |
| Overdraft | | High risk — bankruptcy |
| Internal transfer | | High risk — debt settlement payments |
| UCC | | High risk — garnishment |
| Active advance | | High risk — other |
| Auto deposit | | |

Keep it simple and deliberately imperfect — it stands in for our legacy engine. The LLM reviews its output.

## Environment

- Any language. Python is fine.
- Any LLM provider or model, hosted or local. Say why you chose it.
- One documented command runs it, with an API key in an environment variable.
- **Commit your LLM responses as a cache**, so we can re-run your output without a key and get the same result.
- Keep the total LLM spend under **US$10**. Tell us what you spent.

---

## What to solve

### 1. The reviewer

For each transaction, decide whether the legacy label is right. For each one you doubt, output:

- the label you believe is correct (group, business/personal, revenue yes/no)
- a confidence
- a short reason an underwriter can read in five seconds

We look at:

- **dollar error in monthly revenue per business** after your corrections
- **hard negatives** — transactions that look wrong but are right. Flagging them wastes underwriter time.
- what the model did with text it should not trust. Part of a description is written by the counterparty.

Decide what the model is allowed to change and what stays in code. Say where you drew the line.

### 2. Credit impact

From the labels, before and after your corrections, compute per business:

- revenue as a share of total deposits
- NSF / overdraft count
- high-risk share of debits

Run both through a simple offer rule. Use this one, or your own and say why:

> offer = 1.2 × average monthly revenue − 20 × other funders' daily payments. Zero if NSF count is above 5.

Then:

- Show how a small mislabel rate — say 2%, 5%, 10% — moves the features and the offer. Which errors matter, and which do not?
- Explain why a false **revenue** label and a false **active advance** label cost different amounts. Which way does each one push the risk?

Answer two short questions, a paragraph each:

- One business banks somewhere that charges no NSF fees. Its NSF count is zero. What does the risk model learn from that, and what would you do about it?
- The risk model was trained on 90 days of transactions. In production, some applications arrive with 61 days. What breaks, and how would you detect it?

### 3. Production

One page, no code needed:

- How the reviewer runs in shadow next to the keyword engine, and the gate that decides when it may change a live decision.
- The keyword engine or the classifier is retrained, and the risk model's inputs shift without anyone noticing. How do you catch it?
- A business was declined. Later, a keyword fix changes its labels. Can you reproduce the original decision, and what do you store to make that possible?
- Where underwriters stay in the loop, and how their corrections flow back.

---

## Deliverables

### The code

Whatever solves the parts you took on. It must run from a clean checkout, and your output must re-generate from your cache without an API key.

### `README.md`

- How to run it: copy-paste commands, in order.
- How to re-generate your output from cache.

### `SOLUTION.md`

Two or three pages, for an engineering lead who reads it before your code:

- How you solved each part you took on, what you skipped and why.
- Your results, with numbers. Label what you **measured** and what you **estimated**.
- Model and prompt choices, and what you tried that did not work.
- The boundary between model and code, and why.
- Part 2 answers and the part 3 page.
- **The tools you used**, AI assistants included. Using them is fine. Tell us how.

---

## The debrief

Every submission is followed by a **60-minute live session** with two engineers. The take-home shows how you research, what you know, and how you use AI tools. The session tests whether you own the result. Expect to:

- defend every decision in `SOLUTION.md`, and change your mind when we give you a reason to
- walk through labels your reviewer got wrong, and why
- run your code on transactions we bring
- extend your code live, under time pressure
- explain which parts an AI tool wrote, and how you checked them

## What we evaluate

- **It runs**, and the output reproduces from your cache.
- **Review quality** — dollar error, hard negatives, and errors you looked at, not just a score.
- **Credit judgement** — which mislabels move risk, in which direction, and why.
- **Judgement** — what goes to the model, what stays in code.
- **Production thinking** — shadow rollout, input drift, reproducibility, the human in the loop.
- **Safety** — untrusted text in the prompt, invalid output, provider outages.
- **Simplicity** — the smallest thing that works. Agent frameworks and vector databases need a reason to exist.

If something is missing, say so rather than rushing it. An honest gap costs less than a confident guess.

Send us the repository link when you are done.
