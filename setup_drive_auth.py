import json
import os
import webbrowser

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
HERE   = os.path.dirname(os.path.abspath(__file__))

CLIENT_SECRETS = os.path.join(HERE, "oauth-credentials.json")
TOKEN_PATH     = os.path.join(HERE, ".google-token.json")
URL_FILE       = os.path.join(HERE, ".auth-url.txt")

# Intercept webbrowser.open to save the URL instead of opening a browser
def _save_url(url, *a, **kw):
    with open(URL_FILE, "w") as f:
        f.write(url)
    print("AUTH_URL:" + url, flush=True)
    return True

webbrowser.open        = _save_url
webbrowser.open_new    = _save_url
webbrowser.open_new_tab = _save_url

flow  = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
creds = flow.run_local_server(port=8080, open_browser=True)

token_data = {
    "token":         creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri":     creds.token_uri,
    "client_id":     creds.client_id,
    "client_secret": creds.client_secret,
    "scopes":        list(creds.scopes) if creds.scopes else SCOPES,
}
with open(TOKEN_PATH, "w") as f:
    json.dump(token_data, f, indent=2)

if os.path.exists(URL_FILE):
    os.remove(URL_FILE)

print("TOKEN_SAVED", flush=True)
