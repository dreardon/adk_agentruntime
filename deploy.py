import os
import vertexai
from vertexai import agent_engines
from vertexai import types
from dotenv import load_dotenv
import warnings

warnings.filterwarnings("ignore", category=UserWarning, message=r".*\[EXPERIMENTAL\].*")

# Load environment variables from .env file
load_dotenv()

from email_listing_agent import app

GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET")
AGENT_RUNTIME_DISPLAY_NAME = os.environ.get("AGENT_RUNTIME_DISPLAY_NAME")
MAIL_AUTH_RESOURCE_NAME = os.environ.get("MAIL_AUTH_RESOURCE_NAME")
WEATHER_API_AUTH_RESOURCE_NAME = os.environ.get("WEATHER_API_AUTH_RESOURCE_NAME")

def deploy_agent():
    """Deploys the agent to Gemini Enterprise Agent Runtime with Agent Gateway and Agent Identity."""
    print(f"Initializing Vertex AI Client For Project: {GOOGLE_CLOUD_PROJECT}, Location: {LOCATION}")
    
    # Initialize the Vertex AI Client
    client = vertexai.Client(
        project=GOOGLE_CLOUD_PROJECT,
        location=LOCATION,
        http_options=dict(api_version="v1beta1")
    )

    adk_app = agent_engines.AdkApp(app=app)
    
    # Get the Most Recent Instance Deployment for AGENT_RUNTIME_DISPLAY_NAME, If Available
    print("Checking for Existing Agent Runtime Deployment...")
    agents_iterator = client.agent_engines.list(
        config={
            "filter": f'display_name="{AGENT_RUNTIME_DISPLAY_NAME}"',
        }    
    )

    all_matches = list(agents_iterator)
    if all_matches:
        target_agent = max(all_matches, key=lambda x: x.api_resource.create_time)
    else:
        target_agent = None
    
    config_params={
        "display_name": AGENT_RUNTIME_DISPLAY_NAME,
        "identity_type": types.IdentityType.AGENT_IDENTITY,
        "agent_framework": "google-adk",
        "requirements": ["google-cloud-aiplatform[agent_engines,adk]==1.151.0","google-adk[agent-identity]==1.32.0","httpx==0.28.1", "urllib3>=2.0.0", "cloudpickle", "pydantic"],
        "staging_bucket": STAGING_BUCKET,
        "python_version": "3.13",
        "env_vars": {
            "GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES": "False",
            "MAIL_AUTH_RESOURCE_NAME": os.environ.get("MAIL_AUTH_RESOURCE_NAME"),
            "WEATHER_API_AUTH_RESOURCE_NAME": os.environ.get("WEATHER_API_AUTH_RESOURCE_NAME"),
            "CONTINUE_URI": os.environ.get("CONTINUE_URI"),
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true"
        },
        "extra_packages": ["email_listing_agent"]
    }  
    
    # Create or Update the Agent Runtime
    try:
        if target_agent:
            AGENT_RUNTIME_NAME = target_agent.api_resource.name
            print(f"Found Existing Agent Runtime Deployment ({AGENT_RUNTIME_NAME}). Updating ...")
            remote_app = client.agent_engines.update(
                name=AGENT_RUNTIME_NAME,
                agent=adk_app,
                config=config_params    
            )
            print(f"Agent Runtime Instance Updated Successfully!")
        else:
            print("Agent Runtime Not Found. Creating Agent Runtime Instance...")
            remote_app = client.agent_engines.create(
                agent=adk_app,
                config=config_params     
            )
            print(f"Agent Runtime Instance Created Successfully!")
            print(f"Set the IAM role (roles/iamconnectors.user) on the Agent Identity to use the Auth Provider.")
        print(f"Resource Name: {remote_app.api_resource.name}")
        print(f"Agent Identity: principal://{remote_app.api_resource.spec.effective_identity}")
        return remote_app
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to deploy agent: {str(e)}")
        return None

if __name__ == "__main__":
    deploy_agent()
