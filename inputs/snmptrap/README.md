# Snooze SNMPTrap plugin

Pure python implementation for receiving SNMP traps and sending them to Snooze server.

# Configuration

Configuration is done in a YAML file at `/etc/snooze/snmptrap.yaml` (or the value of the `SNOOZE_SNMPTRAP_CONFIG` environment variable).

Example configuration can be found at [examples/snmptrap.yaml](./examples/snmptrap.yaml).

General options:
* `listening_address` (String, defaults to `0.0.0.0`): Address to listen to.
* `listening_port` (Integer, defaults to `1163`): Port to listen to. Please note than when choosing a port
lower than 1024 (like 163 for instance), you will need to run the process as root.
* `snooze_server` (String): URI of the snooze server to send records to. If not specified, will default to the value in `/etc/snooze/client.yaml`.

SNMP options:
* `mib_dirs` (Array of String, defaults to `['/usr/share/snmp/mibs']`): An array of directory containing MIB files. All MIB file in these directories will be loaded and used to provide MIB names instead of OIDs when creating records.

Worker options:
* `send_workers` (Integer, defaults to `4`): Number of threads to use for sending to snooze server.
