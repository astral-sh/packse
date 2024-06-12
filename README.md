# packse

Python packaging scenarios.

## Installation

Install from PyPI:

```bash
uv pip install packse
```

Once installed, the `packse` command-line interface will be available.

## Usage

### Scenarios

A scenario is a JSON description of a dependency tree.

See [`scenarios/examples/`](./scenarios/examples/)

Each scenario file can contain one or more scenarios.

### Listing scenarios

A list of available scenarios can be printed with the `list` command:

```bash
packse list
```

By default, packse will search for scenarios in the current tree. You may also pass a file to read
from:

```bash
packse list scenarios/examples/example.json
```

Each scenario will be listed with its unique identifier e.g. `example-cd797223`. This is the name of the package
that can be installed to run the scenario once it is built and published.

Each `packse` command supports reading multiple scenario files. For example, with `list`:

```bash
packse list scenarios/examples/example.json scenarios/requires-does-not-exist.json
```

### Viewing scenarios

The dependency tree of a scenario can be previewed using the `view` command:

```
$ packse view scenarios/examples/example.json
example-89cac9f1
├── root
│   └── requires a
│       └── satisfied by a-1.0.0
├── a
│   └── a-1.0.0
│       └── requires b>1.0.0
│           ├── satisfied by b-2.0.0
│           └── satisfied by b-3.0.0
└── b
    ├── b-1.0.0
    ├── b-2.0.0
    │   └── requires c
    │       └── unsatisfied: no versions for package
    └── b-3.0.0
```

Note the `view` command will view all scenarios in a file by default. A single scenario can be viewed by providing
the `--name` option:

```
$ packse view scenarios/examples/example.json --name example
example

This is an example scenario, in which the user depends on a single package `a` which requires `b`

example-89cac9f1
├── root
│   └── requires a
│       └── satisfied by a-1.0.0
├── a
│   └── a-1.0.0
│       └── requires b>1.0.0
│           ├── satisfied by b-2.0.0
│           └── satisfied by b-3.0.0
└── b
    ├── b-1.0.0
    ├── b-2.0.0
    │   └── requires c
    │       └── unsatisfied: no versions for package
    └── b-3.0.0
```

Notice, when a specific scenario is specified, there is more information displayed.

### Building scenarios

A scenario can be used to generate packages and build distributions:

```bash
packse build scenario/example.json
```

The `build/` directory will contain sources for all of the packages in the scenario.
The `dist/` directory will contain built distributions for all of the packages in the scenario.

When a scenario is built, it is given a unique identifier based on a hash of the scenario contents and the project
templates used to generate the packages. Each package and requirement in the scenario will be prefixed with the
identifier. The unique identifier can be excluded using the `--no-hash` argument, however, this will prevent
publishing multiple times to a registry that does not allow overwrites.

The `PACKSE_VERSION_SEED` environment variable can be used to override the seed used to generate the unique
identifier, allowing versions to differ based on information outside of packse.

### Publishing scenarios

Built scenarios can be published to a Python Package Index with the `publish` command:

```bash
packse publish dist/example-cd797223
```

By default, packages are published to the Test PyPI server.

Credentials must be provided via the `PACKSE_PYPI_PASSWORD` environment variable. `PACKSE_PYPI_USERNAME` can be
used to set a username if not using an API token. If using a server which does not require authentication, the
`--anonymous` flag can be passed.

### Running a package index

_Requires installation with the `index` extra_

A local package index can be controlled with the `index` command. For example, to start a local package index:

```bash
packse index up
```

The `--bg` flag can be passed to run the index in the background.
When running an index in the background, state will be stored in the `~/.packse` directory. The `PACKSE_STATE_PATH`
environment variable can be used to change the state path.

Packages can be installed by passing the `--index-url` flag to the installer e.g. with `pip`:

```bash
pip install --index-url http://127.0.0.1:3141 example-0611cb74
```

Packages can be published to the index by providing the `--index-url` and `--anonymous` flags to the `publish` command:

```bash
packse publish dist/example-cd797223 --index-url http://localhost:3141 --anonymous
```

Packages can also be published to the index by placing their distributions in the configured `--dist-dir`. This defaults
to `./dist` which is also the default location used in `packse build`.

By default, the index will fallback to PyPI for missing packages. To test in isolation, use the `--offline` flag.

To stop an index running in the background use `packse index down`:

```
packse index down
```

### Serving scenarios

_Requires installation with the `serve` extra_

The `serve` command can be used to host, build, and publish scenarios in one step.

```bash
packse serve scenarios
```

Packse will watch for changes to the `scenarios` directory, and publish new versions on each change.

Note when developing, it is often useful to use the `--no-hash` flag to avoid having to determine the latest
hash for the scenario.

### Testing scenarios

Published scenarios can then be tested with your choice of package manager.

For example, with `pip`:

```bash
pip install -i https://test.pypi.org/simple/ example-cd797223
```

### Exporting scenarios

Scenario information can be exported with the `packse inspect`. This creates a JSON representation of the scenarios
with additional generated information such as the root package name and the tree displayed during `packse view`.

### Writing new scenarios

Scenario files may contain one or more scenarios written in JSON. See the existing scenarios for examples and
the `Scenario` type for details on the supported schema.
