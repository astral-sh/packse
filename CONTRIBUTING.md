# Contributing

This document outlines a few tips for contributing to packse.

## Running tests

packse uses `pytest`:

```
poetry run pytest
```

## Updating snapshots

If you make changes to the code that results in a snapshot test failing, then
you should examine whether the changes are correct. If so, you can re-run the
tests with the `--snapshot-update` flag:

```
poetry run pytest --snapshot-update
```

And then commit the results. In at least some cases, this may commit a snapshot
that is inconsistent with what CI expects. In this case, you'll want to
manually back out the change. See [this comment][index-incorrect-snapshot] for
an example.

[index-incorrect-snapshot]: https://github.com/astral-sh/packse/pull/175#issuecomment-2056964089
