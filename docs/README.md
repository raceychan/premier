# Premier Documentation

This directory contains the source files for Premier's documentation website, built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

## Development

### Local Development

To serve the documentation locally:

```bash
uv run mkdocs serve
```

This will start a development server at `http://localhost:8000` with live reload.

### Building

To build the static site:

```bash
uv run mkdocs build
```

The built site will be in the `site/` directory.

### Deployment

Documentation is automatically deployed to GitHub Pages when changes are pushed to the `master` branch via the `.github/workflows/docs.yml` GitHub Action.

## Structure

- `index.md` - Homepage
- `installation.md` - Installation guide
- `quickstart.md` - Quick start tutorial
- `configuration.md` - Complete configuration reference
- `web-gui.md` - Web dashboard documentation
- `examples.md` - Examples and use cases
- `changelog.md` - Version history
- `images/` - Screenshots and diagrams

## Configuration

The site configuration is in `mkdocs.yml` at the project root.

## Contributing

When adding new documentation:

1. Create new `.md` files in the `docs/` directory
2. Add them to the `nav` section in `mkdocs.yml`
3. Test locally with `uv run mkdocs serve`
4. Submit a pull request

The documentation uses [GitHub Flavored Markdown](https://github.github.com/gfm/) with additional features from [PyMdown Extensions](https://facelessuser.github.io/pymdown-extensions/).