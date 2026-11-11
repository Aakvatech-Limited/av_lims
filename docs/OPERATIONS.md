# Setup and laboratory workflow

## Configure before operation

1. Install ERPNext and AV LIMS on a disposable development site first.
2. Assign LIMS Technician, LIMS Lead, LIMS Manager and LIMS Approver to the relevant users.
   Use separate people for testing, processing, QA and approval when self-review is disabled.
   System Manager alone is not a laboratory approver; Administrator is the explicit bootstrap account.
3. Review read access to ERPNext masters and set native User Permissions for Lab Division,
   Customer and Project where appropriate. Verify list, report, attachment and API access using
   ordinary users. Do not rely on navigation to grant or restrict access.
4. Create Lab Division, sample types, test definitions, project profiles, sampling locations
   and material lots. Profiles link the existing ERPNext Project/Customer/Company context.
5. Define and approve method versions. Input/output codes must be distinct simple identifiers.
   Formulas support arithmetic, bounded integer powers, `mean`, `min`, `max` and `sqrt`.
   Outputs reference inputs, not other outputs. Approve real scientific procedures and independently
   verified examples; do not treat sample formulas in unit tests as laboratory methods.
6. Approve checklist and project specification versions. Specifications currently implement
   inclusive lower/upper simple-acceptance comparisons only.
7. Populate private calibration/equipment and competency evidence before enabling their gates.
8. Agree partial reporting, self-review, signed authorization, retention, backup, recovery,
   report layout and signature-evidence policies. Confirm the 16 BRD clarification items.
9. Record the approved choices in Lab Settings; only then enable Policies Confirmed.

## Normal operation

1. **Work Request:** retain the test program and its revision; enter requested tests. Retain
   the fee estimate or link a customer Quotation. The form offers Create shortcuts for downstream records.
2. **Work Authorization:** select Contract or Fee Estimate, identify the signed document/version,
   upload private evidence and use Authorize as the approver. Changes to the work scope require renewed authorization.
3. **Samples and Receipt:** register samples against locations/material lots, then put them on
   a receipt with Accepted/On Hold/Rejected decisions and private signed Work Request evidence.
   Receive finalizes the receipt; only Accepted samples progress. Received sample identity is locked.
4. **Inspection plan:** define sample/specimen/execution counts for each obligation, optionally
   scoped to a lot/location. Release the plan. For held obligations, create Lab Hold Point Release
   using the row ID shown by ITP Coverage; the named witness, if configured, must release it.
5. **Specimens and scheduling:** register preparation date, specimen/set identity and conditioning.
   Enter target age and early/late tolerances on the schedule. The system calculates the due window.
6. **Work Plan:** assign received samples, specimens, approved methods and technicians; Release.
7. **Custody:** create the sample CoC referencing the released plan and Activate. Add transfers;
   each named receiver acknowledges their own transfer. Acknowledged events cannot be silently replaced.
8. **Test Execution:** reference the plan, custody, sample/specimen and method. Use Load Method Inputs.
   Enter observations and confirm Value Recorded, including measured zero. Record actual test time,
   equipment and applicable raw evidence, then Complete Raw as the assigned technician.
9. **Complete custody:** acknowledge all transfers and upload completion evidence. Planned raw testing
   must be present before the CoC can be completed.
10. **Process:** the Lead processes frozen observations using the captured method version. This creates
    result values and a digest; a linked age schedule is marked completed.
11. **QA:** select result executions, use Load Checklist and answer each required question. The Manager
    accepts or requires correction. Reviews bind to the exact result digests.
12. **Conformity:** when required, evaluate eligible results against the sample's approved project
    specification. A valid material Fail may be reported; it is not automatically a laboratory error.
13. **Report:** select executions and their accepted QA reviews. Link conformity if reported. Approve
    as the authorized approver. The app checks coverage/holds, freezes the snapshot and saves a private PDF.
14. **Dispatch:** select the current approved report; record recipient, channel and actual delivery
    evidence. Issue only after delivery is recorded. Failed/pending attempts remain unissued draft records.
    No automatic client email is sent by this version.

## Nonconformance and corrections

- The Lead opens a laboratory nonconformance with the affected execution and containment.
- The Manager records corrective action and private completion evidence, then Return to QA.
- If observations need replacing, the Lead reopens custody with a recorded reason, new transfers
  are acknowledged as needed, and a new execution explicitly supersedes the prior execution.
  Earlier raw observations/results remain unchanged. Reopened custody holds affected result release.
- Repeat QA links the corrective action and includes the affected/replacement execution. Close the
  nonconformance only after repeat QA is accepted. Open predecessor nonconformances hold replacements too.
- A report amendment references the earlier approved report and a change reason. The earlier PDF
  is retained. New processed result revisions and approved report replacements block stale dispatch.

## Reports and navigation

Open AV LIMS from Apps. Its Dock opens the module Sidebar and Workspace. Operations are grouped
into intake/planning, testing, review/release, project masters, setup and reports. Child tables are
not shown as independent work screens. Existing personal/site navigation arrangements are retained.

- **Work Register:** source job/program revision information. Work Request status is not yet a computed
  overall completion KPI; inspect related records to determine progress.
- **Test Due Register:** scheduled, overdue and completed age-based tests.
- **Nonconformance Register:** processing/QA issues and closure status.
- **ITP Coverage:** explicitly required versus processed distinct units and hold-point status. This is
  processed-work coverage, not QA acceptance or engineering permission to release construction work.
