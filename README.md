<p align="center"><img src="https://github.com/llvm/circt/blob/main/docs/includes/img/circt-logo.svg" /></p>

# CIRCT Tests

This repository contains various larger-scale tests for the tools provided by the [CIRCT](https://github.com/llvm/circt) project.

## Getting Started

Clone this repository.
Do not recursively clone the submodules, since not all of _their_ submodules are needed.
Use the provided scripts to only grab the submodules that are necessary.

```bash
utils/update-all.sh

# Verilog frontend tests
verilog/sv-tests/install-deps.sh
verilog/sv-tests/run.sh
```

## Repository Structure

- **ext**: Contains all git submodules used by the test suite.
  These can be external test suites, tests, tools, sources, and more.
- **utils**: Utilities to work with the test suite.
  Contains useful scripts to update only the necessary submodules, among other things.
- **verilog**: Tests for the Verilog frontend of CIRCT.

## Verilog

### sv-tests

The `verilog/sv-tests` directory contains scripts to run the [sv-tests](https://github.com/chipsalliance/sv-tests) suite through circt-verilog.
Run the `verilog/sv-tests/install-deps.sh` script once on your machine to install the commonly-needed Python and Perl dependencies.
Then use `verilog/sv-tests/run.sh` to run the entire test suite and generate the following interesting files:

- `ext/sv-tests/out/report/index.html` contains an HTML report of all tests, similar to [sv-tests-results](https://chipsalliance.github.io/sv-tests-results/).
- `ext/sv-tests/out/runs_segfault.txt` contains a list of runs that crashed circt-verilog with a stack trace.
- `ext/sv-tests/out/runs_diagnostics.txt` contains a list of runs that produced errors or warnings.
- `ext/sv-tests/out/errors.txt` contains a list of all errors, ranked from most to least common.

The list of errors is an excellent starting point if you want to contribute to circt-verilog and are looking for the most impactful issues to fix.
Some of these errors can also be produced by Slang, which is often the case if the source code of the test contains issues.
In that case, consider looking at the Slang configuration in `ext/sv-tests/tools/runners/Slang.py` to see if it contains any excludes or special command line arguments that should be added to `ext/sv-tests/tools/runners/circt_verilog.py` as well.

Nirvana is for the `runs_segfault.txt` and `runs_diagnostics.txt` files both to be empty.
That would indicate that circt-verilog happily compiles _everything_ in sv-tests.
We're not there yet.

The most critical issues to fix are the `runs_segfault.txt`.
We definitely do not want to have circt-verilog crash on user input.
