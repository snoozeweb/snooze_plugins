# Google Chat

 This plugin uses Google Chat API to have a chatbot showing Snooze alerts in real time. The chatbot also serves as a frontend for the user that wants to interact these alerts (using Google Pub/Sub set up in the previous section)

## Enable Google Chat API

Go to the [Google Chat API](https://console.cloud.google.com/apis/library/chat.googleapis.com) page

## Configure Google Chat bot

Got the the [Configuration](https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat) page

Configuration hints:
* In _Functionality_, check `App can be messaged directly`
* In _Functionality_, check `App can be added to spaces with multiple users`
* In _Connection settings_, select `Cloud Pub/Sub`
  * Use the Google Pub/Sub _Topic name_ from the previous section ([Link](https://console.cloud.google.com/cloudpubsub/topic))
* In _Permissions_, check `Everyone in Your Organization`
  * For testing purpose, you can either check `Specific people and groups in your domain`  and add up to 5 email addresses (will only work with small Google Chat Spaces)

## Add Google Chatbot to a Space

**IMPORTANT**: When creating a new Google Space, make sure to check `Use threaded replies`. This plugin will not work on spaces that do not use threads

In your Google Space, click on `Add people & apps` then select the chatbot you just created
