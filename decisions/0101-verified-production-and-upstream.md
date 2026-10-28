# 0101 — Publish verified Operator frontend and upstream source

- Owner authorized deployment and upstream publication. Vercel production READY: dpl_8GCBcVWtAzMXBp73b7pYodjWSA16; https://cadiback-web.vercel.app (immutable https://cadiback-q7i721zf2-memy2.vercel.app). Existing production BACKEND_URL retained; no backend/configuration redeploy performed manually.
- Source snapshot pushed to origin/main as 860c927. GitHub initially rejected older unpublished history containing an Asaas token in asaaswebhook.txt. Created a clean fast-forward snapshot on origin/main excluding that file, added its ignore rule, preserved original history locally on local-pre-upstream-20261027 and kept local credentials in ignored files. Local main now tracks the clean upstream. Frontend tree is identical to deployed source076ab24; unrelated existing local tooling deletions and runtime feed cache changes remain uncommitted.
- Published controlled browser checks: availability376, calendar248, finder408 (1032 total) at1440/768/390/320 for guests/members. Real page/health/sports/catalog200; sports320fixtures, catalog12games; protected player401. No live account/payment/bet writes used for QA.
- Existing GitHub Fly Deploy workflow triggered by the upstream push failed because the Fly trial ended and requires a payment method (run40608305916). This is separate from the successful Vercel release; no billing or Fly configuration changes made. Release record commit uses [skip ci] to avoid rerunning that blocked workflow for documentation alone.

Prior local gates: production static build, verifier zero problems, nine Node
test files, core50/backend426. Vercel also built server output successfully.
Production checks use real frontend code with controlled API/session fixtures;
real endpoint smoke is read-only. Browser logs are under /tmp/operator-deployed-*.log.

The upstream snapshot preserves current source while excluding the blocked
credential file and its unpublished ancestry. The archival branch is local only;
no force push or push-protection bypass was used. Original working changes outside
the release scope remain intact.

Fly run: https://github.com/zGabrielR1/cadiback/actions/runs/40608305916
Vercel: https://vercel.com/memy2/cadiback-web/8GCBcVWtAzMXBp73b7pYodjWSA16
