# Validation record

## Executable checks

- Standalone `unittest` suite: calculation precision, recorded zero, missing/duplicate parameters,
  restricted expression syntax, invalid numeric inputs, conformity boundaries and specimen windows.
- Schema/navigation suite: links resolve, child types are correct, controllers exist, fields are
  unique, exports regenerate identically and all user-facing records are reachable.
- Site integration module: method approval/immutability, forged state/output rejection,
  version uniqueness and installed navigation/report records.
- GitHub Actions: standalone checks, source package build, fresh Frappe/ERPNext installation,
  migration and the site integration module.

The authoring workspace has no Frappe bench, MariaDB or Redis. Standalone checks can be run
locally; installation, database tests, PDF generation and browser/ordinary-user checks require
the CI bench or a real development site. CI configuration is not a claim that a workflow passed.

## Required site UAT

1. Install/migrate twice and check no duplicate roles, permissions or navigation resets.
2. Verify each role, company/division restrictions and private attachment access.
3. Complete both authorization alternatives and the full multi-sample workflow.
4. Validate actual method calculations and zero/missing observations independently.
5. Test competency expiry, equipment expiry, specimen windows and wrong project/sample links.
6. Exercise nonconformance, corrective action, custody reopen, replacement result and repeat QA.
7. Demonstrate a valid material Fail can be reported after laboratory QA acceptance.
8. Test incomplete inspection counts, outstanding holds and the named witness check.
9. Generate/reopen the frozen PDF; amend results/reports and reject stale dispatch.
10. Test simultaneous receipt/custody/processing attempts, failed PDF generation and transaction rollback.

Native v16 navigation schemas and export paths were checked against upstream Frappe sources.
The JSON exports were authored in the repository, not exported from a running site.
