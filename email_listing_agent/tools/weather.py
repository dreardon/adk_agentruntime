import httpx
from google.adk.auth.auth_credential import AuthCredential

async def get_current_weather(credential: AuthCredential, location: str = "Reston,VA") -> str:
    """Retrieves the current weather for a given location.
    
    Args:
        credential: The AuthCredential object injected by ADK.
        location: The location to get the weather for (e.g., 'Reston,VA').
    """
    api_key = None
    if getattr(credential, "http", None):
        if getattr(credential.http, "credentials", None) and getattr(credential.http.credentials, "token", None):
            api_key = credential.http.credentials.token
            print(f"Extracted token from credentials: {api_key[:5]}...")
        elif getattr(credential.http, "additional_headers", None):
            api_key = credential.http.additional_headers.get("X-GOOG-API-KEY") or credential.http.additional_headers.get("X-API-Key")
            print(f"Extracted token from additional_headers: {api_key[:5]}...")
                
    if not api_key:
        return "Error: No Weather API Key available"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location}",
                params={
                    "key": api_key,
                    "include": "current",
                    "elements": "remove:stations"
                }
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            return f"Error fetching weather: {e.response.text}"
        except Exception as e:
            return f"An error occurred fetching weather: {str(e)}"
            
        data = response.json()
        current = data.get("currentConditions", {})
        conditions = current.get("conditions", "")
        temp = current.get("temp", "")
        desc = data.get("description", "")
        address = data.get("resolvedAddress", location)
        
        parts = []
        if conditions or temp:
            parts.append(f"Current conditions in {address}: {conditions}, Temperature: {temp}°F.")
        if desc:
            parts.append(f"Forecast: {desc}")
            
        if not parts:
            return f"Weather data received for {address}: {data}"
            
        return " ".join(parts)
