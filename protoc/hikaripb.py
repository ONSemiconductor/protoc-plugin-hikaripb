#!/usr/bin/env python3
# Copyright (c) 2025 Semiconductor Components Industries, LLC ("onsemi")
# SPDX-License-Identifier: GPL-3.0-or-later
r"""protoc plugin that generates the codecs (C, C++, Python) and the documentation of a protocol from its .proto files.

protoc starts the plugin, which reads the request from stdin and writes the response to stdout:

    protoc --plugin=protoc-gen-hikaripb=protoc/hikaripb.py --proto_path=protos \
        --hikaripb_out=type=c,prefix=abc:out protos/message.proto

The options are the key=value pairs in front of the ':' of --hikaripb_out, separated by commas. A key without a value
is a flag, name=false switches it off. With config_file=<file> the options are also read from a JSON file: an option
given on the command line wins over the file, and the file over the defaults. protoc cuts the parameter at the first
':', so a path must not start with a drive letter.

Without arguments the plugin does its work. --help prints this text and the options.
"""

# Standard modules
import argparse
import io
import sys
import logging

# Plugin modules
from google.protobuf.compiler.plugin_pb2 import CodeGeneratorResponse, CodeGeneratorRequest

# Intra-component modules
from config import ConfigError, ConfigManager, options_help
from c import parser as c_parser
from cpp import parser as cpp_parser
from python import parser as py_parser
from sphinxdocs import parser as sphinxdocs_parser

def process_request(request: CodeGeneratorRequest) -> CodeGeneratorResponse:
    # The options come from the parameter of the request and the configuration file it names
    config = ConfigManager.parse(request.parameter)

    # Generate response
    response = CodeGeneratorResponse()
    response.supported_features = CodeGeneratorResponse.FEATURE_PROTO3_OPTIONAL

    match config.type:
        case "c":
            c_parser.generate_c(request, response, config)
        case "cpp":
            cpp_parser.generate_cpp(request, response, config)
        case "py":
            py_parser.generate_py(request, response, config)
        case "sphinxdocs":
            sphinxdocs_parser.generate_sphinxdocs(request, response, config)
        case _:
            raise Exception("Unknown request type")

    # Return response
    return response

if __name__ == "__main__":
    # --help is the only argument: protoc starts the plugin without any
    argparse.ArgumentParser(
        prog="hikaripb.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="options of --hikaripb_out:\n\n" + options_help()).parse_args()

    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='%(message)s')

    # Parse input from stdin
    input_data = io.open(sys.stdin.fileno(), "rb").read()
    request = CodeGeneratorRequest.FromString(input_data)

    # Parse proto files
    try:
        response = process_request(request)
    except ConfigError as error:
        sys.exit(f"hikaripb: {error}")

    # Write response to stdout
    output_data = response.SerializeToString()
    io.open(sys.stdout.fileno(), "wb").write(output_data)        
