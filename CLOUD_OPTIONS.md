# Worker hosting research — 1 October 2026

Decision: retain the temporary PC worker. No new cloud resource or subscription
was created. There is currently no verified replacement meeting all requirements:
no payment card, no subscription, sufficient memory for our models, and unattended
processing of private uploads. The PC must remain on for analysis and export.

| Candidate | Evidence and assessment | Next step |
|---|---|---|
| Hugging Face community GPU grant | Official documentation invites applications. Approval, hardware and duration are not guaranteed. Our ordinary Space/ZeroGPU creation was previously rejected. | A grant is a potential sponsorship route; prepare an application for user review, not an assumed deployment. |
| Modal | Advertises monthly free compute credits, but that is a usage allowance rather than unlimited hosting. No-card eligibility for this account has not been established from official documentation. | Verify actual signup eligibility and hard spending controls before considering deployment. No account created. |
| Cloudflare Workers AI | A free allowance exists for supported models; custom/private requirements require separate review. We have not established support for our forensic models or Python worker. | Possible future model-specific integration, not a verified replacement. |
| PythonAnywhere Free | Documents 100 CPU seconds/day and 512 MB storage, with restricted outbound access. | Reject for the current heavy inference worker. |
| Koyeb Free | Official pricing FAQ requires a card; its free instance has 512 MB RAM and 0.1 vCPU. | Reject under current account and compute constraints. |
| Oracle Always Free | User cannot complete required card verification. | Deferred by user; no signup or provisioning. |

Sources checked:

- https://huggingface.co/docs/hub/main/spaces-gpus
- https://modal.com/pricing
- https://modal.com/docs/guide/billing
- https://developers.cloudflare.com/workers-ai/
- https://developers.cloudflare.com/workers-ai/platform/pricing/
- https://help.pythonanywhere.com/pages/FreeAccountsFeatures
- https://www.pythonanywhere.com/pricing/
- https://www.koyeb.com/docs/faqs/pricing

An institution or sponsor providing an existing machine could also remove the PC
dependency, but no such access is currently available. Notebook sessions and CI
runners are not proposed as permanent hosting workarounds. Further candidates
must pass a real PC-off job test, privacy review, and quota-exhaustion test before
being described as replacements.
