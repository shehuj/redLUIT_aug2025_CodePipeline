# redLUIT — Static Website CI/CD on AWS

[![Deploy](https://github.com/shehuj/redLUIT_aug2025_CodePipeline/actions/workflows/deploy.yml/badge.svg)](https://github.com/shehuj/redLUIT_aug2025_CodePipeline/actions/workflows/deploy.yml)
[![TestsPackage](https://github.com/shehuj/redLUIT_aug2025_CodePipeline/actions/workflows/TestsPackage.yml/badge.svg)](https://github.com/shehuj/redLUIT_aug2025_CodePipeline/actions/workflows/TestsPackage.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

A static website (the Level Up In Tech landing page, `website.html`) delivered by a **GitHub Actions** CI/CD
pipeline to **AWS**. Every change is tested. Pushes to `dev` deploy to **beta** and pushes to `main` deploy
to **prod**. Each environment serves the page from a private S3 bucket through Amazon CloudFront over
HTTPS, and each deployment is recorded in that environment's CloudWatch log group.

## Architecture

```
 feature ──PR──► dev ───────────PR──────────► main
                  │  push                       │  push
                  ▼                             ▼
        ┌─────────────────── deploy.yml ───────────────────┐
        │ tests (TestsPackage.yml: files, flake8, pytest,  │
        │        cfn-lint on Python 3.11–3.13)             │
        │   └─► deploy: CloudFormation stack (site.yaml)   │
        │        ─► s3 sync *.html ─► CloudFront invalidate│
        │        ─► smoke test ─► CloudWatch Logs record   │
        └──────────────────────────────────────────────────┘
                  │                             │
                  ▼                             ▼
         redluit-site-beta              redluit-site-prod
   S3 (private) ◄─OAC─ CloudFront   S3 (private) ◄─OAC─ CloudFront
         logs → BETA_LOG_GROUP          logs → PROD_LOG_GROUP
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `website.html` | Landing page (default root object) |
| `infrastructure/site.yaml` | CloudFormation for one environment: S3 bucket, CloudFront + OAC, bucket policy |
| `.github/workflows/deploy.yml` | CD: on push to `dev`/`main`, run tests, then deploy to beta/prod |
| `.github/workflows/TestsPackage.yml` | CI: runs on every PR, and is called by `deploy.yml` before each deploy |
| `bucketPolicy.json` | Public-read policy for the **legacy** S3 static-website setup (see below) |
| `tests/` | pytest suite: required files, HTML validity/security, bucket-policy guard rails |
| `requirements-dev.txt` | Pinned CI/test tooling |

## Local development

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

python tests/test_required_files.py   # quick pre-check (standard library only)
flake8 .                              # Python lint
pytest -v tests/                      # full test suite
cfn-lint infrastructure/*.yaml        # CloudFormation lint
```

Open `website.html` in a browser to preview your changes.

### What the tests enforce

- Required repository files exist and are not empty
- Every page has an HTML5 doctype, balanced tags, `lang`, a UTF-8 charset, a viewport, a description and a title
- External assets load over HTTPS with Subresource Integrity (`integrity` + `crossorigin`)
- Relative links resolve to files in the repository
- `bucketPolicy.json` grants nothing beyond `s3:GetObject` on objects

## Deployment

Deployment is fully automated by `.github/workflows/deploy.yml`:

| Branch | Environment | CloudFormation stack | Log group secret |
| --- | --- | --- | --- |
| `dev` | `beta` | `redluit-site-beta` | `BETA_LOG_GROUP` |
| `main` | `prod` | `redluit-site-prod` | `PROD_LOG_GROUP` |

On every push to one of these branches the workflow:

1. Runs the full test suite (`TestsPackage.yml`). Nothing deploys if it fails.
2. Creates or updates the environment's CloudFormation stack from `infrastructure/site.yaml`.
3. Syncs only `*.html` to the bucket (`--delete` removes pages deleted from the repo).
4. Invalidates the CloudFront cache.
5. Smoke-tests the site URL.
6. Writes a JSON deployment record to CloudWatch Logs, whether the deploy succeeded or failed.
   The record holds the environment, status, URL, commit, branch, actor and run link. The log group is
   created with 90-day retention if it doesn't exist yet.

The site URL appears on the run summary and under **Deployments** for each GitHub environment. The first
deployment to an environment takes about 5 minutes while CloudFront provisions. You can also start a run
manually from the Actions tab (**Deploy → Run workflow**) on `dev` or `main`.

### Required repository secrets

| Secret | Purpose |
| --- | --- |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Credentials of the deploying IAM user |
| `AWS_REGION` | Region for the stacks and log groups (e.g. `us-east-1`) |
| `BETA_LOG_GROUP` | CloudWatch log group for beta deployment records |
| `PROD_LOG_GROUP` | CloudWatch log group for prod deployment records |

The deploying IAM user needs permission to:

- manage stacks named `redluit-site-*`: `cloudformation:*Stack*`, `cloudformation:*ChangeSet*`, `cloudformation:GetTemplateSummary`
- create and configure the buckets those stacks create: `s3:CreateBucket`, `s3:Put*`, `s3:Get*`, `s3:ListBucket`, `s3:DeleteObject`
- manage the distribution: `cloudfront:*Distribution*`, `cloudfront:*OriginAccessControl*`, `cloudfront:CreateInvalidation`, `cloudfront:TagResource`
- write deployment records: `logs:CreateLogGroup`, `logs:PutRetentionPolicy`, `logs:DescribeLogGroups`, `logs:CreateLogStream`, `logs:PutLogEvents` on the two log groups

### Verifying a deployment

```bash
STACK=redluit-site-prod   # or redluit-site-beta
URL=$(aws cloudformation describe-stacks --stack-name $STACK \
  --query "Stacks[0].Outputs[?OutputKey=='WebsiteUrl'].OutputValue" --output text)
curl -sI "$URL"                  # 200 with strict-transport-security header
curl -sI "$URL/README.md"        # 403: only HTML pages are published

aws logs tail "<PROD_LOG_GROUP value>" --since 1h   # deployment records
```

### Security and operations

- **No public bucket.** CloudFront reads the bucket through Origin Access Control. The bucket has all
  Block Public Access settings on, server-side encryption, versioning (old versions expire after 90 days),
  and a policy that denies non-TLS requests.
- **HTTPS only**, served over HTTP/2 and HTTP/3, with the AWS-managed security headers policy (HSTS,
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).
- **Quality gate**: deploy jobs depend on the full test suite. Only `*.html` is published.
- **Serialized deploys**: one deployment per environment at a time, and a running deploy is never cancelled.
- **Audit trail**: every deployment, successful or not, is logged to CloudWatch, and GitHub environments
  keep a deployment history.
- **Fast rollback**: revert the commit and push. You can also restore a previous object version from the
  versioned bucket.
- The site bucket is **retained** if a stack is deleted, which protects the content from accidental loss.
- **Recommended hardening**: replace the long-lived access keys with GitHub OIDC and an IAM role
  (`aws-actions/configure-aws-credentials` with `role-to-assume`). Also add required reviewers to the
  `prod` environment under **Settings → Environments**.

### Legacy setup (public S3 website endpoint)

The original deployment used an S3 bucket (`myluitwebsite`) with static website hosting and
`bucketPolicy.json` attached. That setup serves over HTTP only and requires turning off Block Public Access.
Once the new prod URL works, retire it and remove the public policy from the legacy bucket.

## Contributing

1. Branch from `dev`, make your change, and run the test suite locally.
2. Open a PR into `dev`. CI must pass.
3. Promote `dev` → `main` with a PR. Merging to `main` deploys to production.

Default reviewers are set in `.github/CODEOWNERS`. Dependabot keeps Actions and pip tooling up to date.

## Security

See [SECURITY.md](SECURITY.md) to report a vulnerability.

## License

[GNU GPL v3](LICENSE)
