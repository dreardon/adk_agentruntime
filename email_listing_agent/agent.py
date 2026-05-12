import os
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents import Agent
from google.adk.auth.credential_manager import CredentialManager
from google.adk.integrations.agent_identity import GcpAuthProvider, GcpAuthProviderScheme
from google.adk.apps import App
from google.adk.auth.auth_tool import AuthConfig
from google.adk.tools.authenticated_function_tool import AuthenticatedFunctionTool
from email_listing_agent.tools import list_recent_emails
from dotenv import load_dotenv

# Load Environment Variables From .env File
load_dotenv()

# Set Variables
AUTH_PROVIDER_RESOURCE_NAME = os.environ.get("AUTH_PROVIDER_RESOURCE_NAME")
CONTINUE_URI = os.environ.get("CONTINUE_URI")

# Register Google Cloud auth provider so the CredentialManager can use it.
CredentialManager.register_auth_provider(GcpAuthProvider())

# Create Auth Config for Mail Access
mail_auth_config = AuthConfig(
    auth_scheme=GcpAuthProviderScheme(
        name=AUTH_PROVIDER_RESOURCE_NAME,
        scopes=["https://mail.google.com/"],
        continue_uri=CONTINUE_URI
    )
)

list_emails_tool = AuthenticatedFunctionTool(
    func=list_recent_emails,
    auth_config=mail_auth_config
)

root_agent = Agent(
    name="email_listing_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a helpful assistant that can read the user's emails. "
        "Use the list_recent_emails tool to fetch the user's latest emails when asked. "
        "Always summarize the findings politely."
    ),
    tools=[list_emails_tool],
)

app = App(
    name="email_listing_agent",
    root_agent=root_agent,
)
