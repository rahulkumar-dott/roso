import os
import shutil
import subprocess
import sys

FALLBACK_GCLOUD = r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
QUOTA_PROJECT = "gen-lang-client-0133745072"


def find_gcloud() -> str:
    found = shutil.which("gcloud")
    if found:
        return found
    if os.path.exists(FALLBACK_GCLOUD):
        return FALLBACK_GCLOUD
    print("Could not find gcloud. Edit FALLBACK_GCLOUD at the top of this script to point at your install.")
    sys.exit(1)


def run(gcloud: str, *args: str) -> None:
    print(f"\n$ gcloud {' '.join(args)}")
    subprocess.run([gcloud, *args], check=True)


def main() -> None:
    gcloud = find_gcloud()
    print(f"Using gcloud at: {gcloud}")

    print("\nStep 1/2: opening a browser window to log in and create Application Default Credentials...")
    run(gcloud, "auth", "application-default", "login")

    adc_path = os.path.join(os.environ["APPDATA"], "gcloud", "application_default_credentials.json")
    if not os.path.exists(adc_path):
        print(f"\nLogin did not produce a credentials file at {adc_path} - something went wrong, stopping.")
        sys.exit(1)
    print(f"\nApplication Default Credentials saved to: {adc_path}")

    print(f"\nStep 2/2: setting the quota project to {QUOTA_PROJECT} (matches the script's project param)...")
    run(gcloud, "auth", "application-default", "set-quota-project", QUOTA_PROJECT)

    print("\nDone. You can now run: uv run python scripts/test_vertex_genai.py")


if __name__ == "__main__":
    main()
