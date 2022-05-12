# Google Chat

This plugin uses Google Chat API to have a chatbot showing Snooze alerts in real time. The chatbot also serves as a frontend for the user that wants to interact these alerts (using Google Pub/Sub set up in the previous section)

## Enable Google Chat API

Go to the [Google Chat API](https://console.cloud.google.com/apis/library/chat.googleapis.com) page

## Configure Google Chat bot

Go to the [Configuration](https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat) page

Configuration hints:
* In _Functionality_, check `App can be messaged directly`
* In _Functionality_, check `App can be added to spaces with multiple users`
* In _Connection settings_, select `Cloud Pub/Sub`
  * Use the Google Pub/Sub _Topic name_ from the previous section ([Link](https://console.cloud.google.com/cloudpubsub/topic))
* In _Permissions_, check `Everyone in Your Organization`
  * For testing purpose, you can either check `Specific people and groups in your domain`  and add up to 5 email addresses (will only work with small Google Chat Spaces)

## Publish and Allowlist

In case you checked the permission `Everyone in Your Organization` earlier, you will need to publish the app and add it to the allowlist

### Configure your OAuth consent screen

This step is required in order to publish the app

Go to the [OAuth consent screen](https://console.cloud.google.com/projectselector2/apis/credentials/consent) configuration page 

Select **Internal** for the _Application type_

Fill up the first form then click on **Save and Continue**

You can leave the second form empty (Scopes)

### Publish the app

Go to the [Google Workspace Marketplace SDK](https://console.cloud.google.com/marketplace/product/google/appsmarket-component.googleapis.com) page and enable it

Open the [Configuration](https://console.cloud.google.com/apis/api/appsmarket-component.googleapis.com/googleapps_sdk) page and publish the app

Configuration hints:
* In _App Configuration_, you can check `Private` for **App Visibility**
* In _App Configuration_, check `Chat App` for **App Integration**
* In _App Configuration_, add `https://www.googleapis.com/auth/chat.bot` to the **OAuth Scopes** list
* In _Store Listing_, fill up all required fields then click on **Publish**

### Add app to the allowlist

From the _Admin console_ Home page, go to **Apps** > **Google Workspace Marketplace apps**

At the top, click on **Google Workspace Marketplace allowlist** > **Add app to allowlist**

Search for the app

Point to the app > click on **Add to allowlist**

## Add Google Chatbot to a Space

**IMPORTANT**: When creating a new Google Space, make sure to check `Use threaded replies`. This plugin will not work on spaces that do not use threads

In your Google Space, click on `Add people & apps` then select the chatbot you just created
