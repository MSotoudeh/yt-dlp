# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's **Report a vulnerability** button (Security tab → Advisories) on this repository, not in a public issue. Include steps to reproduce and the affected version or commit. You can expect an acknowledgement within a week.

Of particular interest: anything that lets a non-allowlisted Telegram user create jobs, leaks the Telegram bot token or a Digital Concert Hall access token (to logs, files, process arguments, MCP replies), lets another extension or website talk to the native-messaging host, or makes the downloaders fetch from unexpected hosts.

## Secrets

Secrets are never stored in this repository. They live only in a git-ignored `.env` / `secrets/` folder or, on the maintainer's machine, in ACL-protected files outside the repository (see `docs/operations.md`). `.env.example` lists variable names only. The Digital Concert Hall token is kept in memory and passed over stdin; it is never written to disk.

## Supported versions

Only the latest commit on `main` is supported.
