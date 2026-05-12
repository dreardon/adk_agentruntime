# Gemini Enterprise Agent Runtime - ADK Agent with 3LO

This repository contains a template for building and deploying an ADK (Agent Development Kit) agent to the Gemini Enterprise Agent Runtime (formerly Agent Engine) on Google Cloud. It demonstrates how to use modern governance and security features, including **Agent Identity** and **3-Legged OAuth (3LO)** via the `GcpAuthProvider`.

## Google Disclaimer
This is not an officially supported Google product

## Prerequisites

Before deploying and running this agent, you must complete some infrastructure setup steps in Google Cloud.

### 1. Set Variables and Enable APIs
The following environment variables are referenced throughout these instructions and in multiple sections. Copy `.env_example`to `.env` and update accordingly.
```bash
GOOGLE_CLOUD_PROJECT= #GCP project ID
GOOGLE_CLOUD_LOCATION= #GCP location e.g. us-central1
STAGING_BUCKET= #GCS bucket for staging agent artifacts
CONTINUE_URI= #OAuth application continue URI
AGENT_RUNTIME_DISPLAY_NAME= #Agent Runtime Display Name
AUTH_PROVIDER_RESOURCE_NAME= #Will be available after Auth Provider creation step below
```
Ensure the following APIs are enabled in your Google Cloud project:
- Vertex AI API
- IAM API
- Gmail API

```bash
gcloud services enable aiplatform.googleapis.com \
iam.googleapis.com gmail.googleapis.com \
--project=$GOOGLE_CLOUD_PROJECT
```

### 2. Set up 3-Legged OAuth (3LO) Client
We'll use Gmail access for this demo. To allow the agent to access a user's emails, you need a Google OAuth 2.0 client.
1. Go to the **APIs & Services > Credentials** page in the Google Cloud Console.
2. Click **Create Credentials > OAuth client ID**.
3. Select **Web application** as the application type.
4. Add your authorized redirect URIs. This should include the `CONTINUE_URI` you will use in the agent configuration (e.g., your frontend application URL that handles the post-auth flow). For Gemini Enterprise this will be `https://vertexaisearch.cloud.google.com/oauth-redirect`. Current guidance can be found in the [Gemini Enterprise Agent Deployment Walkthrough](https://docs.cloud.google.com/gemini/enterprise/internal/agent-deployment-walkthrough).
5. Save the **Client ID** and **Client Secret**. You will need these to configure the Auth Provider.

### 3. Create an Auth Provider in IAM
You need to create an Auth Provider (connector) that references your OAuth client. 
1. Follow the guidance at [Agent Identity Auth Models](https://docs.cloud.google.com/iam/docs/agent-identity-overview#auth-models). For this deployment, we'll use the [3-legged OAuth (3LO) with Auth Manager](https://docs.cloud.google.com/iam/docs/auth-with-3lo) option. This allows the agent to act on behalf of a user based on their explicit consent.
2. We will use the [Google Cloud CLI](https://docs.cloud.google.com/iam/docs/auth-with-3lo#gcloud) instructions to create the Auth Provider. Specific command paramaters are [here](https://docs.cloud.google.com/sdk/gcloud/reference/alpha/agent-identity/connectors/create).
3. Note the full resource name of the created provider. It will look like: `projects/[GOOGLE_CLOUD_PROJECT]/locations/[GOOGLE_CLOUD_LOCATION]/connectors/AUTH_PROVIDER_NAME`.

```bash
export AUTH_PROVIDER_NAME=adk-agentruntime-ge-g-oauth #Set your own value as needed

gcloud alpha agent-identity connectors create $AUTH_PROVIDER_NAME  \
    --location=$GOOGLE_CLOUD_LOCATION \
    --three-legged-oauth-authorization-url="https://accounts.google.com/o/oauth2/v2/auth" \
    --three-legged-oauth-token-url="https://oauth2.googleapis.com/token" \
    --three-legged-oauth-client-id=[OAUTH_CLIENT_ID] \
    --three-legged-oauth-client-secret=[OAUTH_CLIENT_SECRET]    

# Set AUTH_PROVIDER_RESOURCE_NAME in `.env` with the following value
gcloud alpha agent-identity connectors describe $AUTH_PROVIDER_NAME \
    --location=$GOOGLE_CLOUD_LOCATION --format="value(name)"
```

### 4. Agent Configuration and Deployment

Ensure all .env variables are set.

To deploy the agent to Gemini Enterprise Agent Runtime, see the following guide [Agent Identity for Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-identity). The following script will run the deployment. If the Agent Runtime exists, the following `deploy.py` will *update* the deployment. If it doesn't exist, it will *create* a placeholder instance and output the Agent Identity that you'll use to set the `roles/iamconnectors.user` role.

```bash
python -m venv venvs
source venvs/bin/activate
pip install -r requirements.txt
python deploy.py
```

```bash
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --role='roles/iamconnectors.user' \
    --member="principal://agents.global.org-[ORGANIZATION_ID].system.id.goog/resources/aiplatform/projects/[GOOGLE_CLOUD_PROJECT_NUMBER]/locations/$GOOGLE_CLOUD_LOCATION/reasoningEngines/ENGINE_ID"
```
