# Security Policy

This is an educational repository of the Obama corporation team. It is used for application security coursework, so the code is not intended for production use.

## Supported versions

Security fixes are applied only to the latest commit on the `main` branch and to the latest release.

## Reporting a vulnerability

Please do not report security vulnerabilities through public issues or pull requests.

Report a vulnerability privately through GitHub Security Advisories:
https://github.com/obama-organization/hw2/security/advisories/new

Include the affected file or component, steps to reproduce and the expected impact.

We acknowledge a report within 3 days and aim to provide a fix or a mitigation plan within 14 days. We follow coordinated disclosure: the advisory is published after the fix is released, and no later than 90 days after the report.

## Verifying our artifacts

The container image is signed with Sigstore Cosign (keyless) by the `docker-publish.yml` workflow. Verify the signature before using the image:

```bash
cosign verify ghcr.io/obama-organization/hw2:latest \
  --certificate-identity "https://github.com/obama-organization/hw2/.github/workflows/docker-publish.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
```

## Українською

Про вразливості повідомляйте приватно через GitHub Security Advisories за посиланням вище, а не через публічні issue. Ми відповідаємо протягом 3 днів і намагаємося виправити проблему або запропонувати план дій протягом 14 днів.
