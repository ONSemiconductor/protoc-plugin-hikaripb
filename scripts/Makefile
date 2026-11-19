# Portable wrapper around protoc + protoc/hikaripb.py.
#
# Usage:
#   make -C scripts generate PROTO=path/to/file.proto OUT=out/dir [PREFIX=hikaripb] [TYPE=both] [OPTS=...]
#
#   PROTO  - path to the .proto file to compile (required)
#   OUT    - output directory for generated files (required)
#   PREFIX - prefix used for the generated runtime symbols, the C++ namespace,
#            the Python runtime modules and the labels of the Sphinx
#            documentation (default: hikaripb).
#   TYPE   - c | cpp | py | both | sphinxdocs (default: both). "both" means
#            c+py; pass TYPE=cpp explicitly for the self-contained native C++
#            codec (unrelated to the c backend - requires a hand-written
#            <prefix>_config.h, see test/cpp/hikaripb_config.h). sphinxdocs
#            writes Sphinx documentation (MyST Markdown) instead of code.
#   OPTS   - extra --hikaripb_out options appended to every backend, comma
#            separated, e.g. OPTS=single_file=protocol (see docs/content/options.md).

SELF_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ROOT_DIR := $(realpath $(SELF_DIR)/..)
PLUGIN   := $(ROOT_DIR)/protoc/hikaripb.py

PROTOC ?= protoc
PREFIX ?= hikaripb
TYPE   ?= both
OPTS   ?=
comma  := ,
EXTRA  := $(if $(OPTS),$(comma)$(OPTS))

.PHONY: generate check-args

check-args:
ifndef PROTO
	$(error PROTO is not set, e.g. make -C scripts generate PROTO=my.proto OUT=out)
endif
ifndef OUT
	$(error OUT is not set, e.g. make -C scripts generate PROTO=my.proto OUT=out)
endif

generate: check-args
	@mkdir -p $(OUT)
ifneq (,$(filter c both,$(TYPE)))
	$(PROTOC) --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb=$(PLUGIN) \
		--proto_path=$(abspath $(dir $(PROTO))) \
		--hikaripb_out=type=c,prefix=$(PREFIX)$(EXTRA):$(abspath $(OUT)) \
		$(abspath $(PROTO))
endif
ifneq (,$(filter py both,$(TYPE)))
	$(PROTOC) --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb=$(PLUGIN) \
		--proto_path=$(abspath $(dir $(PROTO))) \
		--hikaripb_out=type=py,prefix=$(PREFIX)$(EXTRA):$(abspath $(OUT)) \
		$(abspath $(PROTO))
endif
ifneq (,$(filter cpp,$(TYPE)))
	$(PROTOC) --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb=$(PLUGIN) \
		--proto_path=$(abspath $(dir $(PROTO))) \
		--hikaripb_out=type=cpp,prefix=$(PREFIX)$(EXTRA):$(abspath $(OUT)) \
		$(abspath $(PROTO))
endif
ifneq (,$(filter sphinxdocs,$(TYPE)))
	$(PROTOC) --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb=$(PLUGIN) \
		--proto_path=$(abspath $(dir $(PROTO))) \
		--hikaripb_out=type=sphinxdocs,prefix=$(PREFIX)$(EXTRA):$(abspath $(OUT)) \
		$(abspath $(PROTO))
endif
