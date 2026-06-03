# Security Policy

## Supported Versions

Only the latest release receives security fixes. Older versions are not actively maintained.

| Version | Supported |
|---------|-----------|
| Latest  | ✅        |
| Older   | ❌        |

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not** open a public GitHub issue. Instead, report it privately:

- **GitHub Private Vulnerability Reporting** — Use the [Security tab](../../security/advisories/new) in this repository to submit a private advisory.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- Any suggested mitigations you may have

You can expect an acknowledgement within **72 hours** and a resolution or status update within **14 days**.

## Security Best Practices for Users

### Secrets Management
- **Never** put `amadeus_api_key`, `amadeus_api_secret`, or `webhook_url` directly in `config.json` if that file is committed to version control.
- Use environment variables (`AMADEUS_API_KEY`, `AMADEUS_API_SECRET`, `WEBHOOK_URL`) to inject secrets at runtime — they take precedence over `config.json`.
- Add `config.json` to `.gitignore` if it contains real credentials.

### Docker
- The production image is built on a [distroless](https://github.com/GoogleContainerTools/distroless) base — it contains no shell or package manager, minimising the attack surface.
- Mount `config.json` as a volume rather than baking it into the image:
  ```bash
  docker run -d \
    -e AMADEUS_API_KEY="..." \
    -e AMADEUS_API_SECRET="..." \
    -e WEBHOOK_URL="..." \
    -p 8080:8080 \
    -v $(pwd)/config.json:/app/config.json \
    --name flight-tracker \
    flight-tracker
  ```
- Do not expose port 8080 publicly — the `/status`, `/flights`, and `/calendar` endpoints have no authentication and will reveal your tracked routes and prices to anyone with access.

### Webhook URL
- Treat your webhook URL as a secret. Anyone with the URL can send arbitrary payloads to your notification endpoint.
- Use HTTPS webhook URLs wherever possible.

### Network Exposure
- The built-in web server (port 8080) is intended for **local or private network use only**. Place it behind a reverse proxy with authentication if you need external access.
