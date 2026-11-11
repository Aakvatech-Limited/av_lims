# Requirement coverage and release boundaries

Design references:
- [Business requirements](https://docs.google.com/document/d/1TcjrOpwutexgck7AiMMVy20PuuKsXpkpOUKQNGYuWw4/edit)
- [RTM and open decisions](https://docs.google.com/spreadsheets/d/1JYejhzx_Jk55txv8LY0AGu8P2rtBorM8gfWzNfXfVR0/edit)
- [Solution design](https://docs.google.com/document/d/1J3yXH6846-dzWCVO6HcyyuX85TxHy4_gxj1dpYUWNh8/edit)

| ID | Implemented component | Acceptance still required |
|---|---|---|
| INT-001 | Work Request and requested-test lines | Approved customer form fields |
| INT-002 | Retained fee estimate or customer Quotation link | Fee rules and print template |
| INT-003 | Client test-program attachment/revision | Customer-specific program structure |
| AUT-001 | Contract OR fee-estimate authorization and scope digest | Authority and signature policy |
| SMP-001 | Sample/Receipt acceptance and context checks | Receipt exceptions and physical procedure |
| SMP-002 | Private signed Work Request evidence on receipt | Signed-form equivalence |
| PLN-001 | Released sample/specimen/method/technician assignments | Capacity and rescheduling policy |
| COC-001 | Prepared and activated per-sample custody | Actual CoC template |
| COC-002 | Separate stable sample and custody records | Splitting/collection procedures |
| TST-001 | Execution, raw observations, method/equipment gates | Real test worksheets and method validation |
| COC-003 | Receiver acknowledgements and completion evidence | Completion checklist and signatures |
| DAT-001 | Restricted Decimal calculations and frozen revisions | Independent calculation examples |
| QUA-001 | Approved checklists and result-bound reviews | Checklist content and QA scope |
| NCR-001 | Laboratory nonconformance and release holds | Classifications and dispositions |
| NCR-002 | Corrective action with evidence | Action policy and deadlines |
| NCR-003 | Corrective-action-linked repeat QA and controlled closure | Multi-user exception UAT |
| AUT-002 | Role-controlled frozen report approval and private PDF | Signatory/reporting requirements |
| REL-001 | Current-revision checks and evidenced dispatch | Delivery channels, partial and amended reports |

The initial app includes construction extensions (project locations, lots, specimens,
conditioning, age windows, specifications, ITP counts and hold releases) and optional equipment/
competency enforcement. These additions do not imply client agreement to new scope.

Not yet implemented: offline/mobile synchronization, instrument data connectors, a client portal,
standard-specific worksheet libraries/graphs, automatic quantity-driven sampling, laboratory QC
control charts, uncertainty/guard-band models, accreditation/proficiency-testing management,
calibration scheduling, advanced resource optimization, stock consumption and automated billing.

Full source-to-design mapping is not proof of operational acceptance. Resolve Q01–Q16,
validate configured methods/templates and execute UAT-001–UAT-018 plus permission, revision,
hold-point, calculation, concurrency and PDF tests before production deployment.
