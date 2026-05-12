import os
import sys
import logging

# Extract pyOpenSSL from urllib3 if it was already injected by the server runner,
# restoring the standard library ssl module. We don't disable the OpenSSL module
# itself so it remains importable by google-auth for mTLS channel configuration.
try:
  import urllib3.contrib.pyopenssl
  urllib3.contrib.pyopenssl.extract_from_urllib3()
except Exception:
  pass

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents import Agent
from google.adk.auth.credential_manager import CredentialManager
from google.adk.integrations.agent_identity import GcpAuthProvider, GcpAuthProviderScheme
from google.adk.apps import App
from google.adk.auth.auth_tool import AuthConfig
from google.adk.tools.authenticated_function_tool import AuthenticatedFunctionTool
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from email_listing_agent.tools import list_recent_emails, get_current_weather
from dotenv import load_dotenv
import warnings

warnings.filterwarnings("ignore", category=UserWarning, message=r".*\[EXPERIMENTAL\].*")

logging.getLogger("google_adk").setLevel(logging.DEBUG)

# Load Environment Variables From .env File
load_dotenv(override=True)

# Set Variables
MAIL_AUTH_RESOURCE_NAME = os.environ.get("MAIL_AUTH_RESOURCE_NAME")
WEATHER_API_AUTH_RESOURCE_NAME = os.environ.get("WEATHER_API_AUTH_RESOURCE_NAME")
CONTINUE_URI = os.environ.get("CONTINUE_URI")

# Register Google Cloud auth provider so the CredentialManager can use it.
CredentialManager.register_auth_provider(GcpAuthProvider())

# Create Mail Access Auth Config
mail_auth_config = AuthConfig(
    auth_scheme=GcpAuthProviderScheme(
        name=MAIL_AUTH_RESOURCE_NAME,
        scopes=["https://mail.google.com/"],
        continue_uri=CONTINUE_URI
    )
)

mail_tool = AuthenticatedFunctionTool(
    func=list_recent_emails,
    auth_config=mail_auth_config
)

# Create Weather Access Auth Config
weather_auth_config = AuthConfig(
    auth_scheme=GcpAuthProviderScheme(
        name=WEATHER_API_AUTH_RESOURCE_NAME,
    )
)

weather_tool = AuthenticatedFunctionTool(
    func=get_current_weather,
    auth_config=weather_auth_config
)

root_agent = Agent(
    name="email_listing_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a helpful assistant that can check the weather and read a user's emails. "
        "Based on the user's request, choose the appropriate tool to call: "
        "use get_current_weather to check the weather if the user asks about weather, "
        "or use list_recent_emails to check their emails if the user asks about emails. "
        "Finally, provide a clear and helpful summary of the findings."
    ),
    tools=[weather_tool, mail_tool],
)

app = App(
    name="email_listing_agent",
    root_agent=root_agent,
)
