<p align="center"><img src="https://github.com/llvm/circt/blob/main/docs/includes/img/circt-logo.svg" /></p>

# CIRCT Tests

This repository contains various larger-scale tests for the tools provided by the [CIRCT](https://github.com/llvm/circt) project.

## Getting Started

Clone this repository.
Do not recursively clone the submodules, since not all of _their_ submodules are needed.
Use the provided scripts to only grab the submodules that are necessary.

```bash
utils/update-all.sh
```

## Repository Structure

- **ext**: Contains all git submodules used by the test suite.
  These can be external test suites, tests, tools, sources, and more.
- **utils**: Utilities to work with the test suite.
  Contains useful scripts to update only the necessary submodules, among other things.
