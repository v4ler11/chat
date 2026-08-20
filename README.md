## tmp-python-service

# Usage

1. Clone the repository
```shell
git clone https://git.valerii.casa/valerii/tmp-python-service.git
cd tmp-python-service
```

## Baremetal

2. Install [uv](https://github.com/astral-sh/uv)
```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

3. Install package & deps
```sh
uv venv
uv sync --extra core
```

4. Run the Service
```sh
uv run core
```

## Docker

2. Ensure you have docker, docker compose installed
```sh
docker --version && docker compose version
```
Help: consult [How to install docker, docker compose, ctk](assets/docs/docker-docker-compose-ctl.md)

3. Build an Image and start container
```sh
docker compose up -d
```

# Development

1. Install the package as in baremetal section
2. Switch to development profile
```sh
uv sync --dev
```

### Adding/ Removing packages
```sh
uv add requests --optional core
uv remove request --optional core
```
or adding to a group e.g., development
```sh
uv add requests --dev
uv remove requests --dev
```

### Upgrading a version
1. Bump up version in `pyproject.toml`
2. Execute
```sh
git tag v0.1.4
git push origin v0.1.4
```
Note: GH actions will automatically create and publish an image based on the tag

### Development tools

#### Pyright -- Static Type Checker
```sh
uv run pyright
```

#### Testing
Run all the tests
```sh
uv run pytest
```

Show all testing markers 
```sh
uv run pytest --markers | head -1
```

Run tests assigned to a marker
```sh
uv run pytest -m "marker"
```