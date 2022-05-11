# Google Service Account

This plugin requires a Google service account to be able to use Google Chat API. This page will show you how to create one and retrieve its credentials

## Create a new project

You may skip this part if you have already created a project before

Go to the [Google Project](https://console.cloud.google.com/projectcreate) creation page

Put a _Project name_ then click on **Create**

## Create a service account

Go to the [Credentials](https://console.cloud.google.com/apis/credentials) page

Click on **Create credentials** then click on **Service account**

Put a _Service account name_ then click on **Done**

## Add chat.bot Scope

In order to have the chatbot being able to publish messages, a specific scope needs to be added to the service account

Click on **Edit service account** then go to the **Details** tab

In _Advanced settings_, copy the _Client ID_ then click on **View Google Workspace Admin Console**

In _Security/API Controls/Domain-wide Delegation_, add the _Client ID_ with the scope `https://www.googleapis.com/auth/chat.bot`

## Generate credentials

In the service account configuration, go to the **Keys** tab

Click on **Add Key** then **Create new key**. Select **JSON** as key type

Your service account credentials should be automatically downloaded to your computer. They will look like this:

```
{
  "type": "service_account",
  "project_id": "vital-octagon-***",
  "private_key_id": "***",
  "private_key": "-----BEGIN PRIVATE KEY-----\n***\n-----END PRIVATE KEY-----\n",
  "client_email": "bot-706@vital-octagon-***.iam.gserviceaccount.com",
  "client_id": "***",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/bot-706%40vital-octagon-***.iam.gserviceaccount.com"
}
```
