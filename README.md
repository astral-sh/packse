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

### Building scenarios

A scenario can be used to generate packages and build distributions:

```bash
packse build scenario/example.json
```

The `build/` directory will contain sources for all of the packages in the scenario.
The `dist/` directory will contain built distributions for all of the packages in the scenario.


When a scenario is built, it is given a unique identifier based on a hash of the scenario contents and the project
templates used to generate the packages. Each package in the scenario will include the unique identifier.

The `build` command will print the unique identifier for the scenario e.g. `example-cd797223`. A special entrypoint
package is generated for the scenario which can be used later to install the scenario.

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

### Testing scenarios

Published scenarios can then be tested with your choice of package manager.

For example, with `pip`:

```bash
pip install -i https://test.pypi.org/simple/ example-cd797223
```

### Writing new scenarios

Scenario files may contain one or more scenarios written in JSON.

**Documentation not yet written**
