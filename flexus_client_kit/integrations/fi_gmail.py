import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = "token.json"


def do_stuff():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("/Users/kot/junkyard/_read_gmail2.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    resp = service.users().messages().list(userId="me", q="is:unread", maxResults=10).execute()

    for msg in resp.get("messages", []):
        m = service.users().messages().get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["Subject"]).execute()
        subject = next(h["value"] for h in m["payload"]["headers"] if h["name"] == "Subject")
        print(subject)


# Auth:
#
# Stay “Testing” (what you have) => 7 days, then re‑consent (actually 10 minutes)
# Flip brand to "Production" => Click Publish app → Confirm → fill security form because gmail.readonly is “restricted”
# Workspace service account => Need Cloud Identity / Workspace, admin‑level setup, no consent screen per user
#
#
# Storing emails in a database:
#
# Derived‑data only (cheapest)
# Store just the OpenAI response + Gmail messageId.
# Re-fetch body on demand → no restricted data at rest → audit optional.
#
# Partial redaction
# Strip PII (names, emails) before DB insert.
# Google often waives the CASA fee if stored text is "irreversibly hashed or masked."
#
# Full bodies, encrypted
# Accept the annual CASA audit + policy paperwork.
# Use KMS‑managed keys, access logs, row‑level ACLs.
#
#
# How n8n does it:
#
# n8n Cloud (hosted at n8n.cloud)
# A single, n8n‑owned OAuth brand already verified for restricted Gmail scopes
# The n8n team (yes, they paid the CASA auditors)
# Click Sign‑in with Google → n8n stores your refresh token in its DB
#
# n8n Community
# Self‑hosted n8n Whatever
# OAuth client‑ID you add under Credentials → Google
# You (or skip verification and stay in Testing mode)
# Follow the “Google OAuth2 generic” doc, create your own brand/client, paste ID & secret
#
#
# In Workspace domains you can skip per‑user consent entirely: create a service account + domain‑wide delegation


# Variant 1 — service‑account + domain‑wide delegation
#
# 1. Create a Workspace service account, enable Gmail scopes, and delegate domain‑wide access in the Admin Console.
# 2. Privacy‑policy/ToS links are optional for purely internal tools, but adding stub pages never hurts.
# 3. PII redaction isn’t mandatory inside your own domain, yet you should encrypt stored content and wrap the service‑account key with Cloud KMS.
# 4. Key‑based creds never expire; there's no 180‑day refresh window—rotate or revoke the key on your own schedule.
# Delegate narrowly: in Admin Console → Security ▸ API controls add the SA and scopes, then set the “Impersonation” condition to info@mycompany.com only.
#
# variant 2 — internal OAuth app
#
# 1. Set the OAuth brand to Internal and create a Desktop or Web client; each coworker clicks “Allow” just once.
# 2. A public privacy policy isn’t enforced for Internal apps, but shipping one keeps auditors happy.
# 3. Storing full message bodies is allowed; still encrypt at rest and offer a “delete my data” endpoint if you value goodwill.
# 4. Refresh tokens live indefinitely as long as they’re used at least once every six months—no weekly pop‑ups.
# Log into info@ in a private browser tab. Run your Internal‑brand OAuth flow once; stash the refresh token. Tokens live forever (as long as you hit them every ≤ 6 months).
#
#
# Google KMS
# https://chatgpt.com/share/6886ed0e-8714-8004-b4f8-52ee0909b88d
#
