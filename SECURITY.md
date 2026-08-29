# Security Policy

## Reporting a vulnerability

Please report security issues privately through GitHub's
[**Report a vulnerability**](https://github.com/tmtabor/oss-notifier-agent/security/advisories/new)
button (repository **Security** tab → **Advisories**). Do not open a public issue for
security problems.

You should get an acknowledgement within a few days. If a fix is warranted, it will be
developed under a private advisory and disclosed once a patched release is available.

## Scope

In scope: the pipeline and agent code in this repository — configuration handling, the
GitHub Search API client, the triage agent, and the Postmark email delivery path.

Out of scope: vulnerabilities in the third-party services this project calls (GitHub, the
model providers, Postmark, Logfire) or in their SDKs — report those to the respective
vendors. Misconfiguration of your own deployment (leaked secrets, over-broad watch lists) is
also out of scope.

## Supported versions

This is a template repository; only the latest `main` receives security fixes.
