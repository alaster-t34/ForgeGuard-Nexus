# Security Policy

- Do not expose ForgeGuard directly to the public Internet without authentication, TLS and network segmentation.
- High-risk tools require explicit approval and are disabled from direct model access.
- Store secrets outside source control. Use environment variables or a secret manager.
- Keep edge device permissions least-privileged; do not use world-writable device nodes.
- Preserve raw evidence and audit data as append-only operational records where regulations require it.
- Report vulnerabilities privately to the repository maintainers before public disclosure.
