SECRET_KEY = "dev"
LIMIT_SUBMITTED_BARCODES_TO_PROVIDED = False

# Sample priority
PRIORITY = {
    "1": "low",
    "4": "high"
}

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

# Application (client) ID of app registration
CLIENT_ID = "c163dd4a-0082-4916-8137-c638a80195af"

# Placeholder - for use ONLY during testing.
CLIENT_SECRET = "_iB~_v_250873kNyA5DAGLs323MWOgFz~X"
# In a production app, we recommend you use a more secure method of storing your secret,
# like Azure Key Vault. Or, use an environment variable as described in Flask's documentation:
# https://flask.palletsprojects.com/en/1.1.x/config/#configuring-from-environment-variables
# CLIENT_SECRET = os.getenv("CLIENT_SECRET")
# if not CLIENT_SECRET:
#     raise ValueError("Need to define CLIENT_SECRET environment variable")

# AUTHORITY = "https://login.microsoftonline.com/common"  # For multi-tenant app
AUTHORITY = "https://login.microsoftonline.com/d0155445-8a4c-4780-9c13-33c78f22890e"

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

# Specifies the token cache should be stored in server-side session
SESSION_TYPE = "filesystem"
