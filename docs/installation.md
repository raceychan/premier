# Installation

## Basic Installation

Install Premier using pip:

```bash
pip install premier
```

## Optional Dependencies

### Redis Support

For distributed caching and rate limiting, install with Redis support:

```bash
pip install premier[redis]
```

This enables:
- Distributed caching across multiple instances
- Shared rate limiting across application instances
- Production-ready deployments

### All Dependencies

To install all optional dependencies:

```bash
pip install premier[all]
```

## Development Installation

If you want to contribute to Premier or need the latest development version:

```bash
git clone https://github.com/raceychan/premier.git
cd premier
pip install -e .
```

For development with all dependencies:

```bash
pip install -e .[dev,redis]
```

## Requirements

- **Python**: >= 3.10
- **Redis**: >= 5.0.3 (optional, for distributed deployments)
- **PyYAML**: For YAML configuration support
- **aiohttp**: Optional, for standalone mode HTTP client

## Verification

Verify your installation:

```python
import premier
print(premier.__version__)
```

You should see the version number printed without any import errors.

## Next Steps

After installation, head to the [Quick Start Guide](quickstart.md) to begin using Premier in your application.