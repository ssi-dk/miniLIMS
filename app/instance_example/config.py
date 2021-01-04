# Flask DEBUG mode
DEBUG=False

# Enter a randomly generated string. Used to protect client sessions.
SECRET_KEY = "dev"

# Specifies the token cache should be stored in server-side session
SESSION_TYPE = "filesystem"

# If True, it won't allow supplying lab users to upload a sample without requesting the barcode first.
LIMIT_SUBMITTED_BARCODES_TO_PROVIDED = False

# Sample priority mapping for the samplesheet
PRIORITY = {
    1: "low",
    4: "high"
}

# Samplesheet configuration
SAMPLESHEET_COLUMNS = {
    "required": ["sampleid", "barcode", "organism"],
    "optional": {
        "validate": ["emails", "priority", "supplydate", "costcenter", "comments"],
        "dont_validate": ["supplydate"]
    },
    "custom_mapping": {
        # "expected_column_name_by_minilims": "custom_name"
    }
}

# Specifies if login system should be USER_PASSWORD or MICROSOFT_AUTH
LOGIN_TYPE = "USER_PASSWORD"

# ----- MICROSOFT AUTH START -----
# Application (client) ID of app registration
CLIENT_ID = ""

# Placeholder - for use ONLY during testing.
CLIENT_SECRET = ""
# In a production app, we recommend you use a more secure method of storing your secret,
# like Azure Key Vault. Or, use an environment variable as described in Flask's documentation:
# https://flask.palletsprojects.com/en/1.1.x/config/#configuring-from-environment-variables
# CLIENT_SECRET = os.getenv("CLIENT_SECRET")
# if not CLIENT_SECRET:
#     raise ValueError("Need to define CLIENT_SECRET environment variable")

# AUTHORITY = "https://login.microsoftonline.com/common"  # For multi-tenant app
AUTHORITY = ""

# Used for forming an absolute URL to your redirect URI.
REDIRECT_PATH = "/getAToken"
# The absolute URL must match the redirect URI you set
# in the app's registration in the Azure portal.

# You can find more Microsoft Graph API endpoints from Graph Explorer
# https://developer.microsoft.com/en-us/graph/graph-explorer
# This resource requires no admin consent
ENDPOINT = 'https://graph.microsoft.com/v1.0/me'

# You can find the proper permission names from this document
# https://docs.microsoft.com/en-us/graph/permissions-reference
SCOPE = ["User.ReadBasic.All"]

# ----- MICROSOFT AUTH END -----

