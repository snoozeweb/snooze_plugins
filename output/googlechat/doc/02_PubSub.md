# Google Pub/Sub

Google Pub/Sub is a convenient way for two applications to communicate asynchronously. Once a _topic_ has been created, Google Chat users will be able to _publish_ messages to it (via bot commands). As a _subscriber_, this plugin will regularly pull these messages then call Snooze API accordingly

## Enable Pub/Sub API

Go to the [Pub/Sub API](https://console.cloud.google.com/apis/library/pubsub.googleapis.com) page

## Create a topic/subscription

Go to the [Topics](https://console.cloud.google.com/cloudpubsub/topic) page then click on **Create Topic**

Put a _topic ID_ and leave the first checkbox _Add a default subscription_ checked. Click on **Create Topic**

## Setup permissions

Go to the [Topics](https://console.cloud.google.com/cloudpubsub/topic) page then click on the topic you just created to highlight it

On right tab, click on **Add Principal**

Type the email address of the Google Service Account you created in the previous section ([Link](https://console.cloud.google.com/apis/credentials)). For the role, put `Owner` then click on **Save**

Add another principal: chat-api-push@system.gserviceaccount.com with `Pub/Sub Publisher` role

Go to the [Subcriptions](https://console.cloud.google.com/cloudpubsub/subscription) page then click on the subscription related to the topic you just created to highlight it

Add the principal `Google Service Account Email` as `Owner`  (same as previously)
