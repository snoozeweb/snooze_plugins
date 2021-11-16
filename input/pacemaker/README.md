# Pacemaker input plugin

This input plugin provides a helper script for pacemaker alert system.

# Installation

```bash
pip3 install -U snooze-pacemaker
```

The script file will be installed in `/usr/local/bin/snooze-pacemaker`. Depending
on your OS, it might end up in a different directory, and you might need to adjust
your configuration.

# Configuration

## With `pcs` commands

On RHEL, you can setup alerts with `pcs` commands like so:

Setup a snooze alert:
```
sudo pcs alert create path=/usr/local/bin/snooze-pacemaker id=snooze
```

Setup the recipient for snooze (you will need the ULR of your snooze server):
```
sudo pcs alert recipient add snooze id=example value=https://snooze.example.com:5200
```

When using Pacemaker 1.x, you need to configure the timestamp to a better default:
```
sudo pcs alert update snooze meta timestamp-format="%Y-%m-%dT%H:%M:%S"
```

References:
* https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/7/html/high_availability_add-on_reference/ch-alertscripts-haar

## With `crm` commands

Create a XML config file (`snooze.xml`):
```xml
<configuration>
    <alerts>
        <alert id="snooze" path="/usr/local/bin/snooze">
            <meta_attributes>
                <nvpair id="timestamp-format" name="timestamp-format" value="%Y-%m-%dT%H:%M:%S" />
            </meta_attributes>
            <recipient id="example" value="https://snooze.example.com" />
        </alert>
    </alerts>
</configuration>
```

Then update the CIB:
```bash
crm configure load update snooze.xml
```

References:
* https://clusterlabs.org/pacemaker/doc/deprecated/en-US/Pacemaker/1.1/html/Pacemaker_Explained/ch07.html
