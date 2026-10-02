# Security policy & threat model

## Reporting
Please open a private security advisory on GitHub (or email the maintainer) rather than a public issue.

## Model
| Threat | Mitigation |
|---|---|
| Unauthenticated access | `X-API-Key` RBAC (viewer < analyst < admin); production **fails closed** with no keys; SHA-256 digests, constant-time compare |
| Abuse / DoS | Per-principal-or-IP rate limit in a shared cache (Redis across workers); fake keys fall back to IP buckets; bounded request sizes and list lengths |
| Prompt injection via names/notes/documents | Sanitisation + `<untrusted_data>` framing, injection **detected and scored** as a risk signal, AI evidence capped and unable to lower a score |
| Data exfiltration to third parties | Web search **off by default**; redaction of emails/IDs/accounts/phones before any search; `restrict_external_lookup` hard-disables search for confidential (e.g. open SAR/STR) subjects |
| Log/record tampering | Hash-chained audit log; `GET /api/v1/audit/verify`; publish the head hash (`/audit/head`) to anchor it externally |
| XSS in the UI | Every server-provided string is HTML-escaped (tested with an `<img onerror>` payload) |
| Error disclosure | Generic 500 with an error id; details only in logs (or when `SENTINEL_API_DEBUG=true`) |

## Known limits
- Authentication is API-key based; there is no user directory, SSO or key rotation UI.
- The audit chain proves integrity *given a trusted anchor*; a DBA who rewrites the whole chain can only be caught by comparing against an externally stored head hash.
- Sanctions screening is name-based. Production use needs identifier matching (DOB, registration numbers) and a maintained data feed.
- The bundled sanctions/PEP lists are **synthetic demo data**; `sentinelai sanctions update` loads the official OFAC SDN list.
