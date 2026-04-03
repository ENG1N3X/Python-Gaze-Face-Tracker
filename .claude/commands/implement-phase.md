Implement the following phase for Mac Eye Control: $ARGUMENTS

The detailed plan for this phase already exists in `docs/features/development-plan.md`.
Do NOT run a planner agent — read the plan directly from that file.

Follow this exact workflow:

---

**Step 1 — Read the plan (no agent needed)**

Read `docs/features/development-plan.md` and extract the section for the requested phase.
Save the phase plan text — you will pass it verbatim to the developer and tester agents.

---

**Step 2 — Development (foreground, wait for completion)**

Launch the `developer` agent in **foreground** mode. Pass:
1. The phase plan section from `docs/features/development-plan.md` (verbatim, in full)
2. The instruction to read `CLAUDE.md` before writing any code

Wait for the developer to finish before proceeding to Step 3.

---

**Step 3 — Testing (foreground, wait for completion)**

Launch the `tester` agent in **foreground** mode. Pass:
1. The phase plan section (verbatim)
2. The list of files created or modified by the developer in Step 2

**Testing scope — keep it lean:**
- Write tests only for **critical logic** — not for every line of code
- Per module: 1 happy-path test + max 2 edge cases
- Always run the full existing test suite to catch regressions
- Do NOT test: trivial getters, config key presence, obvious instantiation
- DO test: core algorithms (mapping accuracy, blink state machine, scroll thresholds), error handling (uncalibrated predict, camera failure), round-trip save/load

Total new tests per phase: aim for 15–25, not 50+.

---

**Step 4 — Report**

Summarize:
- What was implemented (files created/modified)
- Test results (passed / failed / errors)
- Any bugs found and fixed
- Any open questions or blockers

Then update `docs/logs/token_usage.md` with the token counts from the developer and tester agents.

If the tester found bugs, launch the `developer` agent again (foreground) with the exact bug report, then re-run the `tester` agent (foreground) to confirm fixes.
