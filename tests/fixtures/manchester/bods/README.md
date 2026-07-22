# Synthetic BODS SIRI-VM fixture

`siri-vm-synthetic.xml` is a schema-faithful **synthetic** fixture created for TrafficTwin.
It is not a BODS download and contains no real vehicle, person, journey, stop, or operator
observation. The `BNSM` value and the words `Bee Network` deliberately exercise the negative
membership contract: neither may activate Bee Network membership while `GA-BEE-1` is open.

The parser test pins the exact SHA-256 of the file. The fixture covers two activities, optional
and absent `Velocity`/`Occupancy`/`DestinationName` values, UTC timestamps, and points inside a
declared Greater Manchester test bounding box.
