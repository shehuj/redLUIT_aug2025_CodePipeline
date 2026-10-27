# redLUIT CodePipeline — Static Website CI/CD

[![TestsPackage](https://github.com/shehuj/redLUIT_aug2025_CodePipeline/actions/workflows/TestsPackage.yml/badge.svg)](https://github.com/shehuj/redLUIT_aug2025_CodePipeline/actions/workflows/TestsPackage.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

A static website (a Level Up In Tech landing page and a résumé) delivered by a CI/CD pipeline built on
**GitHub Actions** and **AWS CodePipeline**. Every change is tested in CI. The pipeline then tests it again,
publishes only the site pages to a private S3 bucket, serves them over HTTPS with Amazon CloudFront, and
invalidates the CDN cache.

## Architecture

```
 developer ──► dev branch ──PR──► main branch
                   │                  │
                   ▼                  ▼
          GitHub Actions CI    AWS CodePipeline (V2)
      (files, flake8, pytest,   ┌──────────────────────────────────────────────┐
           cfn-lint)            │ Source  ─► Test        ─► Deploy             │
                                │ GitHub     CodeBuild      S3 (HTML only)     │
                                │ (CodeConn) buildspec.yml  ─► Invalidate CDN  │
                                └──────────────────────────────────────────────┘
                                                   │
                                                   ▼
                     Private S3 bucket ◄─OAC─ CloudFront (HTTPS, security headers) ◄── visitors
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `website.html` | Landing page (default root object) |
| `myResume.html` | Résumé page |
| `infrastructure/pipeline.yaml` | CloudFormation: S3, CloudFront + OAC, CodeBuild, CodePipeline, IAM |
| `buildspec.yml` | CodeBuild spec for the pipeline's Test stage; outputs only `*.html` |
| `bucketPolicy.json` | Public-read policy for the **legacy** S3 static-website setup (see below) |
| `tests/` | pytest suite: required files, HTML validity/security, bucket-policy guard rails |
| `.github/workflows/TestsPackage.yml` | CI for pushes and PRs to `main` and `dev` |
| `requirements-dev.txt` | Pinned CI/test tooling |

## Local development

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

python tests/test_required_files.py   # quick pre-check
flake8 .                              # Python lint
pytest -v tests/                      # full test suite
cfn-lint infrastructure/*.yaml        # CloudFormation lint
```

Open `website.html` or `myResume.html` in a browser to preview your changes.

### What the tests enforce

- Required repository files exist and are not empty
- Every page has an HTML5 doctype, balanced tags, `lang`, a UTF-8 charset, a viewport, a description and a title
- External assets load over HTTPS with Subresource Integrity (`integrity` + `crossorigin`)
- Relative links between pages resolve
- `bucketPolicy.json` grants nothing beyond `s3:GetObject` on objects

## Deploying to AWS

### 1. Create the GitHub connection (one time)

In the AWS console go to **Developer Tools → Settings → Connections**, create a GitHub connection, and
complete the authorization handshake so its status is **Available**. Copy its ARN.

### 2. Deploy the stack

```bash
aws cloudformation deploy \
  --stack-name redluit-site \
  --template-file infrastructure/pipeline.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      ConnectionArn=arn:aws:codeconnections:us-east-1:123456789012:connection/xxxxxxxx \
      RepositoryId=shehuj/redLUIT_aug2025_CodePipeline \
      BranchName=main

aws cloudformation describe-stacks --stack-name redluit-site \
  --query "Stacks[0].Outputs" --output table
```

The `WebsiteUrl` output is the site's HTTPS address. Each push to `main` then triggers the pipeline.

| Parameter | Default | Description |
| --- | --- | --- |
| `ConnectionArn` | — | ARN of the GitHub connection (required) |
| `RepositoryId` | `shehuj/redLUIT_aug2025_CodePipeline` | `owner/repo` |
| `BranchName` | `main` | Branch that deploys to production |
| `DefaultRootObject` | `website.html` | Page served at `/` |
| `ArtifactRetentionDays` | `30` | Lifecycle expiry for pipeline artifacts |

### Security and operations

- **No public bucket.** CloudFront reads the bucket through Origin Access Control. The bucket has all
  Block Public Access settings on, server-side encryption, versioning (old versions expire after 90 days),
  and a policy that denies non-TLS requests.
- **HTTPS only**, served over HTTP/2 and HTTP/3, with the AWS-managed security headers policy (HSTS,
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).
- **Least-privilege IAM** roles for CodePipeline and CodeBuild, each scoped to this stack's resources.
- **Quality gate**: the deploy stage runs only after the CodeBuild test stage passes. Only `*.html` is
  published, so tests, workflows and policies never reach the website.
- **Fast rollback**: revert the commit on `main` and the pipeline redeploys. You can also restore a
  previous object version from the versioned bucket.
- The site bucket is **retained** if the stack is deleted, which protects the content from accidental loss.

### Legacy setup (public S3 website endpoint)

The original deployment used an S3 bucket (`myluitwebsite`) with static website hosting and
`bucketPolicy.json` attached. Note that this setup:

- serves over HTTP only and requires turning off Block Public Access, and
- publishes the **whole repository** (tests, workflows, README) to the bucket when CodePipeline deploys
  the source artifact directly.

Moving to `infrastructure/pipeline.yaml` is recommended. Once the new `WebsiteUrl` works, disable the old
pipeline and remove the public policy from the legacy bucket.

## Contributing

1. Branch from `dev`, make your change, and run the test suite locally.
2. Open a PR into `dev`. CI must pass.
3. Promote `dev` → `main` with a PR. Merging to `main` deploys to production.

Default reviewers are set in `.github/CODEOWNERS`. Dependabot keeps Actions and pip tooling up to date.

## Security

See [SECURITY.md](SECURITY.md) to report a vulnerability.

## License

[GNU GPL v3](LICENSE)
