# packse

Python packaging scenarios.

## Installation

Only a local installation is supported at this time:

```bash
poetry install
```
Once installed, the `packse` command-line interface will be available.

Depending on your Poetry configuration, you may need to use `poetry run packse` instead or activate Poetry's 
virtual environment.

## Usage

### Scenarios

A scenario is a JSON description of a dependency tree.

See [`scenarios/example.json`](./scenarios/example.json)

Each scenario file can contain one or more scenarios.

### Listing scenarios

A list of available scenarios can be printed with the `list` command:

```bash
packse list
```

By default, packse will search for scenarios in the current tree. You may also pass a file to read 
from:

```bash
packse list scenarios/example.json
```

Each scenario will be listed with its unique identifier e.g. `example-cd797223`. This is the name of the package
that can be installed to run the scenario once it is built and published.

Each `packse` command supports reading multiple scenario files. For example, with `list`:

```bash
packse list scenarios/example.json scenarios/requires-does-not-exist.json
```

### Building scenarios

A scenario can be used to generate packages and build distributions:

```bash
packse build scenario/example.json
```

The `build/` directory will contain sources for all of the packages in the scenario.
The `dist/` directory will contain built distributions for all of the packages in the scenario.

When a scenario is built, it is given a unique identifier based on a hash of the scenario contents and the project
templates used to generate the packages. Each package and requirement in the scenario will be prefixed with the 
identifier.

The `PACKSE_VERSION_SEED` environment variable can be used to override the seed used to generate the unique
identifier, allowing versions to differ based on information outside of packse.

### Viewing scenarios

The dependency tree of a scenario can be previewed using the `view` command:

```
$ packse view scenarios/example.json
example-cd797223
└── a-1.0.0
    └── requires b>=1.0.0
        └── satisfied by b-1.0.0
└── b-1.0.0
```

### Publishing scenarios

Built scenarios can be published to a Python Package Index with the `publish` command:

```bash
packse publish dist/example-cd797223
```

By default, packages are published to the Test PyPI server.

Credentials must be provided via the `PACKSE_PYPI_PASSWORD` environment variable. `PACKSE_PYPI_USERNAME` can be
used to set a username if not using an API token.

### Testing scenarios

Published scenarios can then be tested with your choice of package manager.

For example, with `pip`:

```bash
pip install -i https://test.pypi.org/simple/ example-cd797223
```

### Writing new scenarios

Scenario files may contain one or more scenarios written in JSON.

**Documentation not yet written**
