"""Fetch a fresh VTU.ng JWT token and print it."""
import httpx
import json

username = input("VTU.ng email: ").strip()
password = input("VTU.ng password: ").strip()

resp = httpx.post(
    "https://vtu.ng/wp-json/jwt-auth/v1/token",
    json={"username": username, "password": password},
    timeout=15,
)

data = resp.json()

if resp.status_code == 200 and "token" in data:
    print("\nToken (copy this into Railway as VTU_NG_JWT_TOKEN):\n")
    print(data["token"])
else:
    print("\nFailed:")
    print(json.dumps(data, indent=2))
