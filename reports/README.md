# reports/

Output directory for generated artifacts:

- `latest_report.md` — written here whenever *Download analysis report* is used
  (a copy is always produced in-memory for the browser download as well).
- Screenshots captured during UI verification.

Reports are **generated artifacts, not source data** — the folder is git-ignored
except its own README, and it is safe to delete its contents at any time.
Every report clearly separates:

1. **Computed statistics** (produced by pandas — authoritative numbers)
2. **AI narrative** (optional interpretation, explicitly labelled as such and
   only present when an OpenAI key is configured and the call succeeded)
