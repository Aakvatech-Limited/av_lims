# AV LIMS

Laboratory and construction materials testing management for **Frappe / ERPNext v16**,
developed by Aakvatech Limited. Development branch: **`version-16-hotfix`**.

AV LIMS connects client instructions and signed work authorization to received samples,
specimens, testing, laboratory QA and controlled client reports. Construction records add
project locations, material lots, versioned specifications, conditioning, test-age schedules,
inspection obligations and hold-point release.

## Implemented application scope

- Work requests with retained client test programs and fee-estimate/Quotation references.
- Signed contract **or** fee-estimate authorization bound to the work scope.
- Receipt batches, private signed receipt evidence, accepted/held/rejected samples and lineage.
- Work plans, per-sample custody events and receiver-only acknowledgement.
- Versioned methods with a restricted Decimal calculation engine and explicit recorded-zero handling.
- Frozen raw observations, processing, result revisions and independent QA checklist reviews.
- Laboratory nonconformance, corrective action and repeat QA before closure.
- A **separate** material-conformity evaluation using approved simple-acceptance limits.
- Frozen approved PDFs, report revisions, protected evidence and dispatch records.
- Project/location/material-lot records; specimens, conditioning and age-based test windows.
- Inspection-plan coverage by distinct sample, specimen or execution; witnessed hold releases.
- Equipment-check and technician-competency gates, configurable in Lab Settings.
- Four permission-aware reports: Work Register, Test Due Register, Nonconformance Register,
  and ITP Coverage.
- Frappe v16 Apps entry, Dock, curated Sidebar and Workspace.

This is an initial implementation, **not an accredited or production-validated LIMS**.
Customer procedures, methods, scientific calculations, report formats and policies require
business validation and site UAT. No ASTM/BS/EN method library is supplied or certified.
The original 18 requirements and current boundaries are mapped in [docs/RTM.md](docs/RTM.md).

## Requirements and installation

- Python **3.14**, Frappe **16.55+**, ERPNext **16.x**; MariaDB and Redis as required by the bench.
- A working Frappe PDF renderer is required to approve result reports.
- No Node application dependencies or custom build step are required by AV LIMS itself.

```bash
bench get-app --branch version-16-hotfix https://github.com/Aakvatech-Limited/av_lims
bench --site your.site install-app av_lims
bench --site your.site migrate
```

Installation creates the four LIMS roles and adds read access to linked ERPNext masters,
preserving existing permission rules. It does not assign roles to users, import customer
records, replace site navigation arrangements or confirm operating policies.

Follow [docs/OPERATIONS.md](docs/OPERATIONS.md) for setup and an end-to-end walkthrough.
An administrator must approve the operating choices and enable **Policies Confirmed**
in Lab Settings before operational actions become available. Defaults require signed
authorization, prohibit self-review and require a full planned report; these are provisional
choices to review, not presumed customer agreement. Optional equipment/competency gates
are disabled until their registers are populated and the policy is approved.

## Development and validation

```bash
python -m unittest discover -s tests -v
ruff check .
python -m compileall -q av_lims tools
# On a disposable installed development site:
bench --site test.site set-config allow_tests true
bench --site test.site run-tests --module av_lims.tests.test_site --skip-before-tests
```

`tools/generate_schema.py` regenerates the committed DocType and navigation metadata.
Business controllers are handwritten. The JSON navigation was validated against upstream
v16 schema and export paths; it was not exported from a live site in this workspace.

The GitHub workflow runs standalone checks and a fresh Frappe/ERPNext installation with
site-level tests. Local standalone checks do not establish successful site installation,
PDF rendering, ordinary-user permissions or browser behavior. See [docs/VALIDATION.md](docs/VALIDATION.md).

## Deliberate boundaries

- Dispatch records evidence of actual issuance; the app does **not** automatically email clients.
- Inspection counts are configured explicitly; automatic quantity/frequency-derived sampling is future work.
- Conformity currently supports **Simple Acceptance** only; no uncertainty/guard-band engine.
- No offline app, instrument connectors, client portal, barcode printing, mix-design optimization,
  advanced statistical QC, proficiency-testing system, inventory consumption or billing automation.
- Records use server-controlled action states, not shipped Frappe `Workflow` records. Do not
  add a conflicting external workflow that writes the protected status field.
- Site administrators and database operators remain privileged; application audit history is
  not a claim of tamper-proof storage.

## License

MIT. Copyright Aakvatech Limited.
