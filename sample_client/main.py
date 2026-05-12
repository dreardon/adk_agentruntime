from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import httpx

import google.auth
import google.auth.transport.requests

load_dotenv()

logging.basicConfig(
    level=logging.INFO, stream=sys.stdout, format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("google_adk." + __name__)

app = FastAPI()

AGENT_URL = os.environ.get("AGENT_BACKEND_URL", "http://localhost:8000")


def get_google_auth_token() -> str:
  """Obtains a valid GCP access token using Google default credentials."""
  try:
    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token
  except Exception as e:
    logger.error(f"Failed to retrieve Google default credentials: {e}")
    raise


async def ensure_vertex_session_exists(client: httpx.AsyncClient, headers: dict, user_id: str, session_id: str):
  """Verifies if a session exists and creates it if missing."""
  base_url = AGENT_URL.split(":streamQuery")[0]
  session_url = f"{base_url}/sessions/{session_id}"
  logger.info(f"Checking remote Vertex AI session existence at: {session_url}")
  try:
    resp = await client.get(session_url, headers=headers)
    if resp.status_code == 404:
      create_url = f"{base_url}/sessions?sessionId={session_id}"
      logger.info(f"Session not found. Creating remote session at: {create_url}")
      create_resp = await client.post(
          create_url,
          headers=headers,
          json={"userId": user_id}
      )
      if create_resp.status_code not in [200, 201]:
        body = await create_resp.aread()
        logger.error(f"Failed to create remote session: {create_resp.status_code} - {body.decode()}")
    elif resp.status_code != 200:
      body = await resp.aread()
      logger.error(f"Failed to check remote session: {resp.status_code} - {body.decode()}")
  except Exception as e:
    logger.error(f"Exception during remote session pre-creation: {e}")


@app.post("/chat")
async def chat(request: Request):
  data = await request.json()
  message = data.get("message")
  logger.info(f"Message: {message}")
  function_response = data.get("function_response")
  logger.info(f"Function Response: {function_response}")

  app_name = "email_listing_agent"
  user_id = data.get("user_id", "test-user")
  session_id = data.get("session_id", "default-session-id")

  # Detect if backend endpoint is hosted in Vertex AI Agent Runtime
  is_vertex = "googleapis.com" in AGENT_URL

  if is_vertex:
    # Vertex AI Reasoning Engine streamQuery expects the shape:
    # { "input": { "message": Content, "user_id": str, "session_id": str } }
    message_content = None
    if message:
      message_content = {
          "role": "user",
          "parts": [{"text": message}],
      }
    elif function_response:
      message_content = {
          "role": "user",
          "parts": [{"functionResponse": function_response}],
      }

    payload = {
        "input": {
            "message": message_content,
            "user_id": user_id,
            "session_id": session_id,
        }
    }
  else:
    # Local ADK dev server payload shape:
    payload = {
        "appName": app_name,
        "userId": user_id,
        "sessionId": session_id,
        "streaming": True,
    }
    if message:
      payload["newMessage"] = {
          "role": "user",
          "parts": [{"text": message}],
      }
    elif function_response:
      payload["newMessage"] = {
          "role": "user",
          "parts": [{"functionResponse": function_response}],
      }

  async def proxy_stream():
    headers = {}
    if is_vertex:
      try:
        token = get_google_auth_token()
        headers["Authorization"] = f"Bearer {token}"
      except Exception as e:
        yield f"data: {json.dumps({'error': f'Auth failed: {str(e)}'})}\n\n"
        return

    async with httpx.AsyncClient(timeout=120.0) as client:
      if is_vertex:
        await ensure_vertex_session_exists(client, headers, user_id, session_id)
      else:
        # Local server requires session pre-creation/existence check
        try:
          resp = await client.get(
              f"{AGENT_URL}/apps/{app_name}/users/{user_id}/sessions/{session_id}"
          )
          if resp.status_code == 404:
            await client.post(
                f"{AGENT_URL}/apps/{app_name}/users/{user_id}/sessions/{session_id}"
            )
        except Exception as e:
          logger.warning(f"Local session check failed: {e}")

      url = AGENT_URL if is_vertex else f"{AGENT_URL}/run_sse"

      async with client.stream(
          "POST", url, json=payload, headers=headers
      ) as r:
        if r.status_code != 200:
          err = await r.aread()
          yield f"data: {json.dumps({'error': err.decode()})}\n\n"
          return

        async for line in r.aiter_lines():
          if line:
            yield f"data: {line}\n\n" if line.startswith("{") else f"{line}\n\n"

  return StreamingResponse(proxy_stream(), media_type="text/event-stream")


@app.api_route("/commit", methods=["GET"])
async def commit(request: Request):
  connector = request.query_params.get("auth_provider_name") or request.query_params.get("connector_name")
  user_id = request.cookies.get("user_id")
  payload = {
      "userId": user_id,
      "userIdValidationState": request.query_params.get(
          "user_id_validation_state"
      ),
      "consentNonce": request.cookies.get("consent_nonce"),
  }

  url = f"https://iamconnectorcredentials.googleapis.com/v1alpha/{connector}/credentials:finalize"
  try:
    async with httpx.AsyncClient(timeout=30.0) as client:
      resp = await client.post(url, json=payload)
      resp.raise_for_status()
      resp_data = resp.json()
      logger.info(f"Finalize response: {resp_data}")

      # Check if the response is a long running operation (LRO) and poll if not done
      operation_name = resp_data.get("name")
      done = resp_data.get("done", False)

      if operation_name and not done:
        logger.info(f"Polling long running operation: {operation_name}")
        poll_url = f"https://iamconnectorcredentials.googleapis.com/v1alpha/{operation_name}"
        
        for attempt in range(30):
          await asyncio.sleep(1.0)
          poll_resp = await client.get(poll_url)
          poll_resp.raise_for_status()
          poll_data = poll_resp.json()
          logger.info(f"Poll attempt {attempt + 1}: {poll_data}")
          
          if poll_data.get("done", False):
            if "error" in poll_data:
              err_msg = poll_data["error"].get("message", "Unknown error")
              raise RuntimeError(f"LRO failed: {err_msg}")
            logger.info("LRO completed successfully.")
            break
        else:
          raise TimeoutError("LRO timed out before completion")
  except Exception as e:
    err_text = e.response.text if (hasattr(e, "response") and e.response is not None) else str(e)
    status = e.response.status_code if (hasattr(e, "response") and e.response is not None) else 500
    logger.error(f"Commit failed: {err_text}")
    return HTMLResponse(err_text, status_code=status)

  return HTMLResponse("""
      <script>
          window.close();
      </script>
      <p>Success. You can close this window.</p>
  """)


app.mount("/", StaticFiles(directory="static", html=True), name="static")