# Supabase Auth Email Delivery and Custom SMTP Guide

Last verified: 2026-11-24 (Asia/Calcutta)

This guide covers ClientExplain AI's hosted Supabase Auth email delivery. It does not authorize changing the hosted project, sending paid email, disabling confirmation, or storing provider credentials in the application.

## Current observed configuration

The public hosted Auth settings endpoint was inspected with the existing publishable key. Values were summarized without recording the project URL or key.

| Setting | Observed |
|---|---|
| Auth settings endpoint | Reachable |
| Email provider enabled | Yes |
| New signups disabled | No |
| Email auto-confirm | No — confirmation remains required |
| Application SMTP environment variables | None |
| Supabase management access token | Not available locally |
| Last delivery attempt | HTTP 429 `over_email_send_rate_limit` before an email was sent |

**Provider classification:** the available evidence is consistent with Supabase's built-in/default email provider. This is an inference, not a management-confirmed setting: the public Auth settings response does not reveal the selected SMTP provider, and service-role/publishable keys cannot read hosted project management configuration or Auth logs.

Supabase currently documents the built-in provider as best-effort, restricted to authorized organization addresses, and limited to **2 Auth emails per hour across the project**. The configured `rate_limit_email_sent`, SMTP fields, and current provider can be confirmed in **Authentication → Rate Limits**, **Authentication → Emails → SMTP Settings**, or with the Supabase Management API. The Management API exposes configured limits, not the remaining live token/quota balance.

Official references:

- [Send emails with custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp)
- [Auth rate limits](https://supabase.com/docs/guides/auth/rate-limits)
- [Test hosted Auth flows](https://supabase.com/docs/guides/auth/testing-auth-flows)
- [Troubleshoot missing Auth emails](https://supabase.com/docs/guides/troubleshooting/not-receiving-auth-emails-from-the-supabase-project-OFSNzw)

## Non-mutating checks

Preferred Dashboard checks:

1. Open **Authentication → Emails → SMTP Settings** and record whether custom SMTP is enabled. Do not save changes.
2. Open **Authentication → Rate Limits** and record the configured email-sent limit. Do not increase it without reviewing the provider's real allowance and abuse controls.
3. Open **Logs → Auth Logs** and filter the time of the failed attempt for `over_email_send_rate_limit`. Do not copy email addresses, confirmation links, tokens, or request bodies into reports.
4. If custom SMTP is enabled, inspect the email provider's delivery/suppression logs without exposing recipient addresses.

Optional read-only Management API check, only when an approved Supabase personal access token is already available:

```powershell
# Store these only in an ignored D:\ClientExplain-Ai\.env.smtp.local file.
# SUPABASE_ACCESS_TOKEN=
# SUPABASE_PROJECT_REF=

$values = @{}
Get-Content -LiteralPath '.env.smtp.local' | ForEach-Object {
    if ($_ -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        $values[$matches[1]] = $matches[2]
    }
}

$headers = @{ Authorization = "Bearer $($values.SUPABASE_ACCESS_TOKEN)" }
$config = Invoke-RestMethod `
    -Uri "https://api.supabase.com/v1/projects/$($values.SUPABASE_PROJECT_REF)/config/auth" `
    -Headers $headers

$config.PSObject.Properties |
    Where-Object { $_.Name -like 'rate_limit_*' -or $_.Name -eq 'smtp_host' } |
    ForEach-Object {
        if ($_.Name -eq 'smtp_host') {
            [pscustomobject]@{ Name = 'custom_smtp_configured'; Value = -not [string]::IsNullOrWhiteSpace($_.Value) }
        } else {
            [pscustomobject]@{ Name = $_.Name; Value = $_.Value }
        }
    }
```

Never print `smtp_user`, `smtp_pass`, access tokens, project keys, recipient addresses, confirmation links, or session tokens.

## Approval-gated custom SMTP preparation

Custom SMTP is configured in hosted Supabase, not in the Next.js browser bundle or FastAPI runtime. Do not add SMTP credentials to `.env`, `apps/web/.env.local`, `NEXT_PUBLIC_*`, Compose, or Git.

Before changing anything:

1. Select a transactional provider that supports SMTP, such as Resend, Postmark, AWS SES, SendGrid, ZeptoMail, or Brevo.
2. Confirm its pricing, sandbox restrictions, allowed recipients, regional/data-processing terms, and sending limits.
3. Prepare a dedicated authentication subdomain and From address, for example `no-reply@auth.example.test`; do not reuse a marketing sender.
4. Configure and validate SPF, DKIM, and DMARC with the provider.
5. Obtain explicit approval for the provider, expected cost, sender domain, and one verification email.

Use the Supabase Dashboard where possible:

1. Go to **Authentication → Emails → SMTP Settings**.
2. Enable custom SMTP.
3. Enter sender email/name, SMTP host, port, username, and password from the approved provider.
4. Keep **Confirm email** enabled and `mailer_autoconfirm=false`.
5. Save only after approval.
6. Review **Authentication → Rate Limits**. Supabase documents an initial custom-SMTP email limit of 30 per hour; choose the lowest limit sufficient for the approved verification and no higher than the provider allowance.
7. Perform exactly one disposable signup, then inspect Supabase Auth logs and provider delivery logs.

If an approved automation path is required, store values only in ignored `.env.smtp.local` using the repository's uppercase underscore convention:

```dotenv
SUPABASE_ACCESS_TOKEN=
SUPABASE_PROJECT_REF=
SUPABASE_SMTP_ADMIN_EMAIL=
SUPABASE_SMTP_HOST=
SUPABASE_SMTP_PORT=587
SUPABASE_SMTP_USER=
SUPABASE_SMTP_PASS=
SUPABASE_SMTP_SENDER_NAME=ClientExplain AI
SUPABASE_RATE_LIMIT_EMAIL_SENT=30
```

The corresponding Management API fields are `external_email_enabled`, `mailer_secure_email_change_enabled`, `mailer_autoconfirm`, `smtp_admin_email`, `smtp_host`, `smtp_port`, `smtp_user`, `smtp_pass`, `smtp_sender_name`, and `rate_limit_email_sent`. Any PATCH is a live external change and requires explicit approval; this repository intentionally provides no automatic mutation script.

## Single-attempt acceptance procedure

Only after Dashboard/Management evidence shows a usable provider and configured allowance:

1. Prepare one fresh disposable, non-production mailbox controlled by the tester.
2. Register once through the real `/register` page while retaining the browser PKCE state.
3. Open only the newly delivered confirmation link.
4. Verify callback routing, backend identity, authenticated session, reload persistence, and normal logout.
5. Delete exact test records/account where supported and safe.
6. Record sanitized timestamps, HTTP status, destination route, session result, logout result, provider/log result, and cleanup counts.

Do not resend, recover, or register another address as a quota probe. Until this procedure succeeds, Step 2.2 remains BLOCKED.
