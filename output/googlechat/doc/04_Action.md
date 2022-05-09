# Snooze Action

For Snooze server to be able to send alerts to this plugin, you need to configure a _Webhook Action_ in SnoozeWeb

## Create Action

In SnoozeWeb, go to the _Actions_ tab then click on **New**

Configuration hints:
* In _Action_, select `Call a webhook`
* In _URL_, put the alert enpoint of the plugin's daemon (by default: http://localhost:5201/alert)
* In _Payload_, put `{"spaces": ["spaces/********"], "alert": {{ __self__  | tojson() }} }`
  * Replace `spaces/********` with the Space ID created in the previous section
* Check `Inject Response`
* Check `Batch` if you want multiple alerts to be grouped in the same thread

## Create Notification

In SnoozeWeb, go to the _Notifications_ tab then click on **New** or **Edit** an existing notification
In _Actions_, select the one you just created
