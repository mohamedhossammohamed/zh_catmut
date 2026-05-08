# Publishing zh-catmut to PyPI

This repository is prepared for PyPI distribution through GitHub Actions and PyPI Trusted Publishing.

## User install target

The public install command is:

```bash
python -m pip install -e ".[test]"
python -m pytest -q
(cd native && zig build test)
python -m pip install zh-catmut
```

The Python import name is:

```python
import zh_catmut
```

Installed users can verify the wheel with:

```bash
zh-catmut doctor
```

## Local package checks

From the repository root:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
python -m pip install --force-reinstall dist/*.whl
zh-catmut doctor
```

If building from source, Zig must be on `PATH` or supplied through `ZIG=/path/to/zig`.

## GitHub Actions

The repository has two package-oriented workflows:

- `.github/workflows/ci.yml`: runs native Zig tests, Python integration tests, package build checks, wheel install verification, and `zh-catmut doctor`.
- `.github/workflows/publish.yml`: builds wheels on Linux, macOS, and Windows; builds an sdist; checks artifacts; and publishes to TestPyPI or PyPI.

## Trusted Publishing setup

Configure trusted publishers on PyPI/TestPyPI instead of storing API tokens in GitHub secrets.

Use these values:

- Owner: `mohamedhossammohamed`
- Repository: `zh_catmut`
- Workflow: `publish.yml`
- Environment for PyPI: `pypi`
- Environment for TestPyPI: `testpypi`
- Package name: `zh-catmut`

## Release flow

1. Confirm `pyproject.toml` has the intended version.
2. Push to `main` and wait for package CI to pass.
3. Run **Publish Python Package** manually with `target=testpypi`.
4. Install from TestPyPI in a clean environment:

   ```bash
   python -m pip install \
     --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ \
     zh-catmut
   zh-catmut doctor
   ```

5. If TestPyPI works, create a GitHub release or manually run the workflow with `target=pypi`.
6. Verify the public install:

   ```bash
   python -m pip install zh-catmut
   zh-catmut doctor
   ```

## Indexing and discoverability checklist

If `pip install zh-catmut` or PyPI search cannot find the project, first confirm whether it exists on the package index:

```bash
python - <<'PY'
import urllib.error
import urllib.request

for url in (
    "https://pypi.org/pypi/zh-catmut/json",
    "https://test.pypi.org/pypi/zh-catmut/json",
):
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            print(url, response.status)
    except urllib.error.HTTPError as exc:
        print(url, exc.code)
PY
```

`404` means the package has not been published to that index yet. Search engines and mirrors cannot index it until the publish workflow succeeds.

For GitHub and GitHub Pages discoverability:

1. Set the GitHub repository description and homepage URL in the repository settings.
2. Add relevant repository topics such as `pandas`, `categorical`, `numpy`, `zig`, `native-extension`, and `python`.
3. Confirm GitHub Pages serves `robots.txt` and `sitemap.xml`.
4. Submit `https://mohamedhossammohamed.github.io/zh_catmut/sitemap.xml` to search engines if immediate crawling is important.
5. Allow time for crawlers to index a new repository and Pages site.
