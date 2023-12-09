import pathlib

# The absolute path to this module
__module_path__ = pathlib.Path(__file__).parent

# The absolute path to the root of the repository, only valid for use during development
__development_base_path__ = __module_path__.parents[1]

del pathlib
