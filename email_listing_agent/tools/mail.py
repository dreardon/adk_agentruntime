import httpx
from google.adk.auth.auth_credential import AuthCredential

async def list_recent_emails(credential: AuthCredential, max_results: int = 5) -> str:
    """Lists the snippets of the user's most recent emails.
    
    Args:
        credential: The AuthCredential object injected by ADK.
        max_results: The maximum number of emails to retrieve.
    """
    token = None
    if credential.http.credentials:
        token = credential.http.credentials.token
    
    if not token:
        return "Error: No authentication token available. Please authenticate first."
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=headers,
                params={"maxResults": max_results},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            return f"Error fetching message list: {e.response.text}"
        except Exception as e:
            return f"An error occurred: {str(e)}"
        
        messages = response.json().get("messages", [])
        if not messages:
            return "No emails found."
        
        results = []
        for msg in messages:
            msg_id = msg["id"]
            try:
                msg_resp = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
                    headers=headers,
                )
                msg_resp.raise_for_status()
                msg_data = msg_resp.json()
                snippet = msg_data.get("snippet", "")
                results.append(f"- {snippet}")
            except Exception as e:
                results.append(f"- [Error fetching message {msg_id}: {str(e)}]")
        
        return "\n".join(results)
