MAKEFLAGS := --jobs=$(shell nproc 2>/dev/null || echo 1)

BUILD_DIR := build

.PHONY: all test run stack coverage clean docs examples

all: test

# Generate the bindings of test/proto (codegen), then build + run the criterion/Python interop test suite
# (see test/Makefile).
test:
	$(MAKE) -C test ROOT=$(CURDIR) test

run:
	$(MAKE) -C test ROOT=$(CURDIR) run

# Worst-case stack usage report for the generated C encode/decode runtime.
stack:
	$(MAKE) -C test ROOT=$(CURDIR) stack

# Line-coverage HTML report for the test suite.
coverage:
	$(MAKE) -C test ROOT=$(CURDIR) coverage

# Generate the bindings of examples/proto and build the C and C++ examples into
# build/examples (see examples/README.md).
examples:
	sh examples/build.sh

# Build the documentation site into build/site (needs docs/requirements.txt), as the Docs workflow does.
docs:
	mkdocs build --strict -f docs/mkdocs.yml

clean:
	rm -rf $(BUILD_DIR)
	$(MAKE) -C test ROOT=$(CURDIR) clean
