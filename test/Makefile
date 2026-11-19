MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
SELF_DIR     := $(patsubst %/,%,$(MAKEFILE_DIR))
ROOT         ?= $(realpath $(SELF_DIR)/..)

CC       ?= gcc
CXX      ?= g++
PROTOC   ?= protoc
PYTHON   ?= python3

PLUGIN     := $(ROOT)/protoc/hikaripb.py
PROTO_DIR  := $(SELF_DIR)/proto
# every generator compiles all schemas, including the ones in sub-directories (shared/common.proto)
PROTO_FILES := $(wildcard $(PROTO_DIR)/*.proto $(PROTO_DIR)/*/*.proto)
# The message the c and cpp generators cannot represent: Node contains itself. It only exists in the
# python output (the option value is quoted in the recipes, '|' separates several names).
IGNORE     := scalarpkg_Node

BUILD_DIR    := $(ROOT)/build/test
GEN_C_DIR    := $(BUILD_DIR)/generated/c
GEN_CPP_DIR  := $(BUILD_DIR)/generated/cpp
GEN_PY_DIR   := $(BUILD_DIR)/generated/py
# python output compiled with Cython, protoc's own python output (independent reference implementation
# of the wire format used by the python tests) and the single_file=all variants of every generator
GEN_PY_CY_DIR      := $(BUILD_DIR)/generated/py_cython
GEN_PY_REF_DIR     := $(BUILD_DIR)/generated/py_ref
GEN_PY_SINGLE_DIR  := $(BUILD_DIR)/generated/py_single
GEN_C_SINGLE_DIR   := $(BUILD_DIR)/generated/c_single
GEN_CPP_SINGLE_DIR := $(BUILD_DIR)/generated/cpp_single
INTEROP_DIR  := $(BUILD_DIR)/interop
OBJ_C_DIR    := $(BUILD_DIR)/obj/c
OBJ_CPP_DIR  := $(BUILD_DIR)/obj/cpp
OBJ_C_SINGLE_DIR   := $(BUILD_DIR)/obj/c_single
OBJ_CPP_SINGLE_DIR := $(BUILD_DIR)/obj/cpp_single

TOOLS_DIR := $(SELF_DIR)/tools
# Every generator uses the schemas in test/proto; each generator's own
# fixtures/config/tests live in its own folder (test/c, test/cpp, test/py).
# The documentation generator (type=sphinxdocs) has its own schemas and tests in test/sphinx.
C_DIR   := $(SELF_DIR)/c
CPP_DIR := $(SELF_DIR)/cpp
PY_DIR  := $(SELF_DIR)/py
SPHINX_DIR := $(SELF_DIR)/sphinx
CONFIG_DIR := $(SELF_DIR)/config
# The interpreter that builds and loads the compiled codec; needs Cython and setuptools (optional)
CYTHON_PYTHON ?= $(PYTHON)
HAVE_CYTHON   := $(shell $(CYTHON_PYTHON) -c "import Cython, setuptools" >/dev/null 2>&1 && echo 1)

# The generated runtime takes nothing from the C library by default (see <prefix>_config_default.h), so the C and
# the C++ sources only need their own generated dirs.
INCLUDE_FLAGS := -I$(C_DIR) -I$(GEN_C_DIR)
# The cpp generator (protoc/cpp, a faithful port of the reference protolib
# generator) emits its own self-contained hikaripb:: C++ runtime + message.pb.h
# (default prefix, so the sources include hikaripb_config.h); it does not use the C output.
INCLUDE_FLAGS_CPP := -I$(CPP_DIR) -I$(GEN_CPP_DIR)
# -Wno-unused-parameter: the generated inline setters only reference their
# WrHandle parameter inside SAMPLE_DEBUG-only assertions.
CFLAGS := -std=c11 -Wall -Wextra -Werror -Wno-unused-parameter -g -O0
CXXFLAGS := -std=c++17 -Wall -Wextra -Werror -Wno-unused-parameter -g -O0
ifeq ($(coverage),1)
CFLAGS += -fprofile-arcs -ftest-coverage
CXXFLAGS += -fprofile-arcs -ftest-coverage
endif

CRITERION_CFLAGS  := $(shell pkg-config --cflags criterion 2>/dev/null || echo "")
CRITERION_LDFLAGS := $(shell pkg-config --libs criterion 2>/dev/null || echo "-lcriterion")

GCOV_DIR  := $(BUILD_DIR)/coverage
LCOV_INFO := $(GCOV_DIR)/coverage.info
HTML_DIR  := $(GCOV_DIR)/html

STACK_BUILD_DIR := $(BUILD_DIR)/stack
STACK_CFLAGS := -std=c11 -Wall -Wextra -Wno-unused-parameter -O1 -fno-inline -fstack-usage
STACK_ROOTS  := sample_decode sample_encode_varint_u32

.PHONY: all build test run stack analyze sanitize coverage clean codegen codegen_c codegen_cpp codegen_py _build \
	codegen_single codegen_c_single codegen_cpp_single codegen_py_single py_cython test_py test_py_cython _test_py_cython \
	test_sphinx test_config

all: build

# ----------------------------------------------------------------------------
# Code generation - regenerate the C, C++ and Python bindings from test/proto
# ----------------------------------------------------------------------------
codegen: codegen_c codegen_cpp codegen_py codegen_single

codegen_c: $(PROTO_FILES)
	rm -rf $(GEN_C_DIR)
	mkdir -p $(GEN_C_DIR)
	$(PROTOC) --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb=$(PLUGIN) \
		--proto_path=$(abspath $(PROTO_DIR)) \
		'--hikaripb_out=type=c,prefix=sample,ignore=$(IGNORE):$(abspath $(GEN_C_DIR))' \
		$(PROTO_FILES)

codegen_cpp: $(PROTO_FILES)
	rm -rf $(GEN_CPP_DIR)
	mkdir -p $(GEN_CPP_DIR)
	$(PROTOC) --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb=$(PLUGIN) \
		--proto_path=$(abspath $(PROTO_DIR)) \
		'--hikaripb_out=type=cpp,ignore=$(IGNORE):$(abspath $(GEN_CPP_DIR))' \
		$(PROTO_FILES)

codegen_py: $(PROTO_FILES)
	rm -rf $(GEN_PY_DIR) $(GEN_PY_REF_DIR)
	mkdir -p $(GEN_PY_DIR) $(GEN_PY_REF_DIR)
	$(PROTOC) --experimental_allow_proto3_optional \
		--proto_path=$(abspath $(PROTO_DIR)) \
		--plugin=protoc-gen-hikaripb=$(PLUGIN) \
		--hikaripb_out=type=py,prefix=sample:$(abspath $(GEN_PY_DIR)) \
		$(PROTO_FILES)
	$(PROTOC) --experimental_allow_proto3_optional \
		--proto_path=$(abspath $(PROTO_DIR)) \
		--python_out=$(abspath $(GEN_PY_REF_DIR)) \
		$(PROTO_FILES)

# single_file=all merges every .proto file into one output (C: sample_all.pb.h/.c,
# C++: all.pb.h, python: all_pb.py) instead of one output per .proto file
codegen_single: codegen_c_single codegen_cpp_single codegen_py_single

codegen_c_single: $(PROTO_FILES)
	rm -rf $(GEN_C_SINGLE_DIR)
	mkdir -p $(GEN_C_SINGLE_DIR)
	$(PROTOC) --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb=$(PLUGIN) \
		--proto_path=$(abspath $(PROTO_DIR)) \
		'--hikaripb_out=type=c,prefix=sample,single_file=all,ignore=$(IGNORE):$(abspath $(GEN_C_SINGLE_DIR))' \
		$(PROTO_FILES)

codegen_cpp_single: $(PROTO_FILES)
	rm -rf $(GEN_CPP_SINGLE_DIR)
	mkdir -p $(GEN_CPP_SINGLE_DIR)
	$(PROTOC) --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb=$(PLUGIN) \
		--proto_path=$(abspath $(PROTO_DIR)) \
		'--hikaripb_out=type=cpp,single_file=all,ignore=$(IGNORE):$(abspath $(GEN_CPP_SINGLE_DIR))' \
		$(PROTO_FILES)

codegen_py_single: $(PROTO_FILES)
	rm -rf $(GEN_PY_SINGLE_DIR)
	mkdir -p $(GEN_PY_SINGLE_DIR)
	$(PROTOC) --experimental_allow_proto3_optional \
		--proto_path=$(abspath $(PROTO_DIR)) \
		--plugin=protoc-gen-hikaripb=$(PLUGIN) \
		--hikaripb_out=type=py,single_file=all:$(abspath $(GEN_PY_SINGLE_DIR)) \
		$(PROTO_FILES)

# ----------------------------------------------------------------------------
# Build the criterion test binaries
# (two-phase: the generated *.c list can only be discovered after codegen_c
#  has actually run, so re-invoke make once codegen is done)
# ----------------------------------------------------------------------------
build: codegen
	$(MAKE) -f $(firstword $(MAKEFILE_LIST)) ROOT=$(ROOT) coverage=$(coverage) _build

vpath %.c $(C_DIR) $(GEN_C_DIR) $(wildcard $(GEN_C_DIR)/*/)
vpath %.cc $(CPP_DIR) $(GEN_CPP_DIR)

# the schemas of sub-directories (shared/common.proto) are generated into sub-directories
GEN_C_SRCS  := $(wildcard $(GEN_C_DIR)/*.c $(GEN_C_DIR)/*/*.c)
# callback_support.c provides callbackpkg_CallbackMsg_value_callback, which
# every binary needs at link time (sample_callback.pb.o's descriptor table
# takes its address regardless of whether the message is ever decoded).
COMMON_SRCS := $(C_DIR)/test_io.c $(C_DIR)/callback_support.c
# Objects shared by every C binary are compiled once so gcov merges coverage
# counts across all the encode/decode/depth/errors/callback test runs instead
# of overwriting them.
SHARED_OBJS := $(addprefix $(OBJ_C_DIR)/,$(notdir $(GEN_C_SRCS:.c=.o)) $(notdir $(COMMON_SRCS:.c=.o)))

# The cpp generator's only non-header-only source is hikaripb_bindings.cc (the
# message-id -> descriptor dispatch table); shared by every cpp binary, along
# with callback_support.cc for the same reason as callback_support.c above.
GEN_CPP_SRCS     := $(wildcard $(GEN_CPP_DIR)/*.cc)
CPP_COMMON_SRCS  := $(CPP_DIR)/callback_support.cc
CPP_SHARED_OBJS  := $(addprefix $(OBJ_CPP_DIR)/,$(notdir $(GEN_CPP_SRCS:.cc=.o)) $(notdir $(CPP_COMMON_SRCS:.cc=.o)))

C_BINS   := test_encode test_decode test_depth test_errors test_callback test_nested test_empty
CPP_BINS := test_encode_cpp test_decode_cpp test_depth_cpp test_errors_cpp test_callback_cpp test_nested_cpp test_empty_cpp
# Built from the single_file=all output instead (see the single-file rules below)
SINGLE_BINS := test_single test_single_cpp

_build: $(addprefix $(BUILD_DIR)/,$(C_BINS) $(CPP_BINS) $(SINGLE_BINS))

$(OBJ_C_DIR)/%.o: %.c
	@mkdir -p $(OBJ_C_DIR)
	$(CC) $(INCLUDE_FLAGS) $(CFLAGS) $(CRITERION_CFLAGS) -c $< -o $@

$(OBJ_CPP_DIR)/%.o: %.cc
	@mkdir -p $(OBJ_CPP_DIR)
	$(CXX) $(INCLUDE_FLAGS_CPP) $(CXXFLAGS) $(CRITERION_CFLAGS) -c $< -o $@

$(BUILD_DIR)/test_encode: $(OBJ_C_DIR)/test_encode.o $(SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_decode: $(OBJ_C_DIR)/test_decode.o $(SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_depth: $(OBJ_C_DIR)/test_depth.o $(SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_errors: $(OBJ_C_DIR)/test_errors.o $(SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_callback: $(OBJ_C_DIR)/test_callback.o $(SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_nested: $(OBJ_C_DIR)/test_nested.o $(SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_empty: $(OBJ_C_DIR)/test_empty.o $(SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_encode_cpp: $(OBJ_CPP_DIR)/test_encode_cpp.o $(CPP_SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_decode_cpp: $(OBJ_CPP_DIR)/test_decode_cpp.o $(CPP_SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_depth_cpp: $(OBJ_CPP_DIR)/test_depth_cpp.o $(CPP_SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_errors_cpp: $(OBJ_CPP_DIR)/test_errors_cpp.o $(CPP_SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_callback_cpp: $(OBJ_CPP_DIR)/test_callback_cpp.o $(CPP_SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_nested_cpp: $(OBJ_CPP_DIR)/test_nested_cpp.o $(CPP_SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_empty_cpp: $(OBJ_CPP_DIR)/test_empty_cpp.o $(CPP_SHARED_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

# ----------------------------------------------------------------------------
# single_file=all smoke tests: the same runtime, but one generated header/source
# pair instead of one pair per .proto file. Own object directories and include
# paths, since the generated runtime files exist twice (same names).
# ----------------------------------------------------------------------------
INCLUDE_FLAGS_SINGLE     := -I$(C_DIR) -I$(GEN_C_SINGLE_DIR) -DCALLBACK_SUPPORT_PB_HEADER='"sample_all.pb.h"'
INCLUDE_FLAGS_CPP_SINGLE := -I$(CPP_DIR) -I$(GEN_CPP_SINGLE_DIR) -DCALLBACK_SUPPORT_PB_HEADER='"all.pb.h"'

GEN_C_SINGLE_OBJS   := $(patsubst %.c,%.o,$(addprefix $(OBJ_C_SINGLE_DIR)/,$(notdir $(wildcard $(GEN_C_SINGLE_DIR)/*.c))))
C_SINGLE_OBJS       := $(GEN_C_SINGLE_OBJS) $(addprefix $(OBJ_C_SINGLE_DIR)/,test_io.o callback_support.o)
GEN_CPP_SINGLE_OBJS := $(patsubst %.cc,%.o,$(addprefix $(OBJ_CPP_SINGLE_DIR)/,$(notdir $(wildcard $(GEN_CPP_SINGLE_DIR)/*.cc))))
CPP_SINGLE_OBJS     := $(GEN_CPP_SINGLE_OBJS) $(OBJ_CPP_SINGLE_DIR)/callback_support.o

$(GEN_C_SINGLE_OBJS): $(OBJ_C_SINGLE_DIR)/%.o: $(GEN_C_SINGLE_DIR)/%.c
	@mkdir -p $(OBJ_C_SINGLE_DIR)
	$(CC) $(INCLUDE_FLAGS_SINGLE) $(CFLAGS) $(CRITERION_CFLAGS) -c $< -o $@

$(OBJ_C_SINGLE_DIR)/%.o: $(C_DIR)/%.c
	@mkdir -p $(OBJ_C_SINGLE_DIR)
	$(CC) $(INCLUDE_FLAGS_SINGLE) $(CFLAGS) $(CRITERION_CFLAGS) -c $< -o $@

$(GEN_CPP_SINGLE_OBJS): $(OBJ_CPP_SINGLE_DIR)/%.o: $(GEN_CPP_SINGLE_DIR)/%.cc
	@mkdir -p $(OBJ_CPP_SINGLE_DIR)
	$(CXX) $(INCLUDE_FLAGS_CPP_SINGLE) $(CXXFLAGS) $(CRITERION_CFLAGS) -c $< -o $@

$(OBJ_CPP_SINGLE_DIR)/%.o: $(CPP_DIR)/%.cc
	@mkdir -p $(OBJ_CPP_SINGLE_DIR)
	$(CXX) $(INCLUDE_FLAGS_CPP_SINGLE) $(CXXFLAGS) $(CRITERION_CFLAGS) -c $< -o $@

$(BUILD_DIR)/test_single: $(OBJ_C_SINGLE_DIR)/test_single.o $(C_SINGLE_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

$(BUILD_DIR)/test_single_cpp: $(OBJ_CPP_SINGLE_DIR)/test_single_cpp.o $(CPP_SINGLE_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $^ $(CRITERION_LDFLAGS) $(if $(filter 1,$(coverage)),--coverage -lgcov,) -o $@

# ----------------------------------------------------------------------------
# Python tests: the generated native codec is tested as pure python and - when Cython and a C
# compiler are available - compiled with <prefix>_build_ext.py. Both runs execute the same tests.
# ----------------------------------------------------------------------------
PY_TEST_ENV = HIKARIPB_PY_REF_DIR=$(abspath $(GEN_PY_REF_DIR)) HIKARIPB_PY_SINGLE_DIR=$(abspath $(GEN_PY_SINGLE_DIR)) \
	HIKARIPB_PLUGIN=$(PLUGIN) PROTOC=$(PROTOC)
# $(1) generated python dir, $(2) expected HIKARIPB_EXPECT_COMPILED value, $(3) interpreter
PY_UNITTEST = HIKARIPB_PY_DIR=$(abspath $(1)) HIKARIPB_EXPECT_COMPILED=$(2) $(PY_TEST_ENV) \
	$(3) -m unittest discover -s $(PY_DIR) -p 'test_*.py'

test_py: codegen_py codegen_py_single
	$(call PY_UNITTEST,$(GEN_PY_DIR),0,$(PYTHON))

# Build the compiled flavour; only produces output when Cython is installed
py_cython: codegen_py
ifeq ($(HAVE_CYTHON),1)
	rm -rf $(GEN_PY_CY_DIR)
	cp -r $(GEN_PY_DIR) $(GEN_PY_CY_DIR)
	$(CYTHON_PYTHON) $(GEN_PY_CY_DIR)/sample_build_ext.py
else
	@echo "py_cython: Cython/setuptools not found for $(CYTHON_PYTHON), skipping the compiled codec"
endif

test_py_cython: py_cython codegen_py_single
	$(MAKE) -f $(firstword $(MAKEFILE_LIST)) ROOT=$(ROOT) _test_py_cython

# The tests only, against the already built GEN_PY_CY_DIR
_test_py_cython:
ifeq ($(HAVE_CYTHON),1)
	$(call PY_UNITTEST,$(GEN_PY_CY_DIR),1,$(CYTHON_PYTHON))
endif

# The documentation generator: unit tests of the comment conversion and protoc runs on its own schemas. The
# Sphinx builds are skipped when the interpreter has no sphinx and myst_parser (SPHINX_PYTHON selects another).
SPHINX_PYTHON ?= $(PYTHON)

test_sphinx:
	HIKARIPB_PLUGIN=$(PLUGIN) PROTOC=$(PROTOC) $(SPHINX_PYTHON) -m unittest discover -s $(SPHINX_DIR) -p 'test_*.py'

# The configuration manager (protoc/config.py): unit tests of the options and the configuration file, and protoc runs
# that read a configuration file. The tests of the names and of the comments of the generated C and C++ code are in
# the same folder.
test_config:
	HIKARIPB_PLUGIN=$(PLUGIN) PROTOC=$(PROTOC) $(PYTHON) -m unittest discover -s $(CONFIG_DIR) -p 'test_*.py'

# ----------------------------------------------------------------------------
# make test / make run - encode in C/C++, verify + re-encode in Python, decode
# in C/C++; the depth/errors/callback/single binaries are self-contained (no
# Python interop involved, they exercise internal decoder limits/behavior).
# The python suite (test/py) then runs against the pure python and, if Cython
# is installed, the compiled codec.
# ----------------------------------------------------------------------------
test: run

run: build py_cython
	@mkdir -p $(INTEROP_DIR)
	SAMPLE_INTEROP_DIR=$(abspath $(INTEROP_DIR)) sh $(TOOLS_DIR)/suite_run.sh $(BUILD_DIR)/test_encode
	SAMPLE_INTEROP_DIR=$(abspath $(INTEROP_DIR)) sh $(TOOLS_DIR)/suite_run.sh $(BUILD_DIR)/test_encode_cpp
	PYTHONPATH=$(abspath $(PY_DIR)) $(PYTHON) $(PY_DIR)/check_interop.py \
		$(abspath $(GEN_PY_DIR)) $(abspath $(INTEROP_DIR))
ifeq ($(HAVE_CYTHON),1)
	PYTHONPATH=$(abspath $(PY_DIR)) $(CYTHON_PYTHON) $(PY_DIR)/check_interop.py \
		$(abspath $(GEN_PY_CY_DIR)) $(abspath $(INTEROP_DIR)) encoded_from_python_cython.bin
	cmp $(INTEROP_DIR)/encoded_from_python.bin $(INTEROP_DIR)/encoded_from_python_cython.bin
	for name in scalars choice repeats textlists; do \
		cmp $(INTEROP_DIR)/$${name}_from_python.bin $(INTEROP_DIR)/$${name}_from_python_cython.bin || exit 1; \
	done
endif
	SAMPLE_INTEROP_DIR=$(abspath $(INTEROP_DIR)) sh $(TOOLS_DIR)/suite_run.sh $(BUILD_DIR)/test_decode
	SAMPLE_INTEROP_DIR=$(abspath $(INTEROP_DIR)) sh $(TOOLS_DIR)/suite_run.sh $(BUILD_DIR)/test_decode_cpp
	sh $(TOOLS_DIR)/suite_run.sh $(BUILD_DIR)/test_depth $(BUILD_DIR)/test_errors $(BUILD_DIR)/test_callback $(BUILD_DIR)/test_nested $(BUILD_DIR)/test_empty $(BUILD_DIR)/test_single
	sh $(TOOLS_DIR)/suite_run.sh $(BUILD_DIR)/test_depth_cpp $(BUILD_DIR)/test_errors_cpp $(BUILD_DIR)/test_callback_cpp $(BUILD_DIR)/test_nested_cpp $(BUILD_DIR)/test_empty_cpp $(BUILD_DIR)/test_single_cpp
	$(MAKE) -f $(firstword $(MAKEFILE_LIST)) ROOT=$(ROOT) test_py
	$(MAKE) -f $(firstword $(MAKEFILE_LIST)) ROOT=$(ROOT) _test_py_cython
	$(MAKE) -f $(firstword $(MAKEFILE_LIST)) ROOT=$(ROOT) test_config
	$(MAKE) -f $(firstword $(MAKEFILE_LIST)) ROOT=$(ROOT) test_sphinx

# ----------------------------------------------------------------------------
# make stack - worst-case stack depth of the generated encode/decode runtime
# ----------------------------------------------------------------------------
stack: codegen_c
	sh $(TOOLS_DIR)/stack_build.sh "$(CC)" "$(STACK_BUILD_DIR)" "$(STACK_CFLAGS)" "$(INCLUDE_FLAGS)" $(GEN_C_DIR) $(filter-out $(C_DIR)/test_single.c,$(wildcard $(C_DIR)/*.c))
	sh $(TOOLS_DIR)/stack_run.sh $(TOOLS_DIR)/stack_usage.py $(STACK_BUILD_DIR) "--top 1 -v" $(STACK_ROOTS)

# ----------------------------------------------------------------------------
# make analyze - static analysis of the generated C and C++ code: strict compiler warnings, clang-tidy and, for C,
# the MISRA C:2012 addon of cppcheck, each with the test configuration and with the second configuration in
# alt/ (every switch on); C++ also with the library defaults in defaults/ (callbacks off). See tools/static_analysis.sh
# for the tools and the environment variables.
# ----------------------------------------------------------------------------
analyze: codegen_c codegen_cpp
	MISRA_CONFIG_DIRS=$(C_DIR)/alt sh $(TOOLS_DIR)/static_analysis.sh c $(GEN_C_DIR) $(C_DIR) $(C_DIR)/alt
	sh $(TOOLS_DIR)/static_analysis.sh cpp $(GEN_CPP_DIR) $(CPP_DIR) $(CPP_DIR)/alt $(CPP_DIR)/defaults

# ----------------------------------------------------------------------------
# make sanitize - all the tests with AddressSanitizer and UndefinedBehaviorSanitizer (in an own build directory):
# any finding aborts the test
# ----------------------------------------------------------------------------
SANITIZE_FLAGS := -fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer

sanitize:
	$(MAKE) -f $(firstword $(MAKEFILE_LIST)) ROOT=$(ROOT) BUILD_DIR=$(BUILD_DIR)_sanitize \
		CFLAGS="$(CFLAGS) $(SANITIZE_FLAGS)" CXXFLAGS="$(CXXFLAGS) $(SANITIZE_FLAGS)" run

# ----------------------------------------------------------------------------
# make coverage - rebuild with gcov instrumentation, run, then render HTML
# ----------------------------------------------------------------------------
coverage: clean
	$(MAKE) -f $(firstword $(MAKEFILE_LIST)) ROOT=$(ROOT) coverage=1 run
	sh $(TOOLS_DIR)/suite_coverage.sh \
		$(GCOV_DIR) $(LCOV_INFO) $(HTML_DIR) $(BUILD_DIR) \
		-- '/usr/*' '*/generated/*'

clean:
	rm -rf $(BUILD_DIR)
