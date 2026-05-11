from __future__ import annotations

from .calendar_filter import SCOPES
from .config import Settings
from .warning_filters import quiet_dependency_warnings


def main() -> None:
    quiet_dependency_warnings()
    from google_auth_oauthlib.flow import InstalledAppFlow

    settings = Settings.from_env()
    if not settings.google_credentials_path.exists():
        raise SystemExit(
            "Google OAuth client file not found at %s. Download a desktop OAuth client as credentials.json."
            % settings.google_credentials_path
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(settings.google_credentials_path), SCOPES)
    credentials = flow.run_local_server(port=0)
    settings.google_token_path.parent.mkdir(parents=True, exist_ok=True)
    settings.google_token_path.write_text(credentials.to_json())
    print("Saved Google Calendar token to %s" % settings.google_token_path)


if __name__ == "__main__":
    main()
