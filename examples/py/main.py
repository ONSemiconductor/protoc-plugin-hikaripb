"""Python example: build, encode, decode and print a weather.Report with the generated bindings.

The code generated from proto/weather.proto lives in build/examples/generated/py, run
examples/build first (see ../README.md).
"""

import os
import sys

# VS Code resolves these imports through python.analysis.extraPaths in .vscode/settings.json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build", "examples", "generated", "py"))

from weather_pb import Reading, Report, Unit  # noqa: E402
from weather_py_codec import DecodeError  # noqa: E402


def main() -> int:
    # Encode: fields are plain attributes, nothing is encoded until serialize() is called.
    # The comments of weather.proto are the docstrings: hover over a name in VS Code to read them.
    # Every field can be given to the constructor, a repeated field takes a list of messages.
    report = Report(
        station="roof-1",
        readings=[Reading(sensor_id=1, temperature=215, unit=Unit.UNIT_CELSIUS, humidity=48, label="roof")],
    )
    report.readings.add(sensor_id=2, temperature=-35, label="shed")  # creates and appends, no humidity
    report.note = "calibrated"  # a oneof: setting one member replaces the other

    data = report.serialize()
    print(f"encoded {len(data)} bytes")

    # Decode: a malformed message raises DecodeError.
    try:
        decoded = Report().deserialize(data)
    except DecodeError as error:
        print(f"decode error {error.code.name}: {error}", file=sys.stderr)
        return 1

    print(f"station {decoded.station}")
    for reading in decoded.readings:
        text = f"sensor {reading.sensor_id} ({reading.label}): {reading.temperature} tenths"
        if reading.has_humidity():  # optional fields have a has_<field>() method
            text += f", humidity {reading.humidity}%"
        print(text)
    if decoded.has_note():
        print(f"note {decoded.note}")

    print()
    decoded.print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
