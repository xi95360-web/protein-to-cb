# Contributing and maintenance

Use this repository to maintain the Codex workflow, public-database connector, installation scripts, and documentation. Report reproducible problems through [GitHub Issues](https://github.com/xi95360-web/protein-to-cb/issues), and propose changes in a branch and pull request.

## Documentation and user experience

Keep repository documentation, maintenance notes, examples, and user-facing software messages in English. The installed skill should still respond in the user's language. Explain the workflow in terms of protein identity, reference states, coverage, and score interpretation before introducing implementation details.

When changing a command, file path, tool argument, or output field, update the corresponding README section and supporting documentation. Preserve the distinction between technical readiness, a model-derived signal, and independent biological evidence.

## Working locally

Follow the setup instructions in the [README](README.md). After editing the workflow, run:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

If you reused a compatible runtime, substitute its interpreter. GitHub Actions runs these lightweight tests on pushes and pull requests.

Changes to the scientific wrapper, dependencies, source pins, model artifacts, or structure parsing also require appropriate real-server and numerical checks:

```sh
.venv/bin/python scripts/check_runtime.py --score
```

For database-connector changes, run `scripts/check_runtime.py --network` and inspect the returned identity, pagination, metadata, and provenance. Use focused tests for changed behavior; documentation-only edits do not require rerunning model scoring.

## Scientific source and dependency updates

The original scientific implementation is pinned in `backend/SOURCE_PROVENANCE.json`. Preserve upstream attribution and licenses. Review upstream changes before updating source or the bundled wheel, record new revisions and hashes, and validate numerical behavior. Do not change expected-score fixtures merely to make a failing comparison pass.

Keep the [validation scope](docs/validation.md) accurate. Distinguish platforms and behaviors that were actually tested from those that remain unverified. A software test passing does not validate a new protein's functional predictions.

## Configuration and distribution

Installer changes must preserve unrelated Codex settings, maintain backup behavior, and handle existing connections explicitly. Repository updates do not automatically deploy to an installed Codex skill or replace a user's runtime; review configuration and skill differences before migrating an existing installation.

Keep virtual environments, `.runtime.json`, credentials, personal Codex settings, paper PDFs, and local run outputs out of commits. Public test fixtures should have a documented source and retain their provenance or checksums where applicable.

Before publishing a change, review the diff, check relative documentation links and example commands, and describe the relevant validation in the commit or pull request. Use [docs/scoring.md](docs/scoring.md) for score semantics and biological interpretation limits.
