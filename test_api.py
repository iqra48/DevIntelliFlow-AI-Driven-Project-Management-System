import requests
import json

payload = {
    "requirements": [
        {
            "id": "REQ_001",
            "requirement": "The system shall allow users to log in with valid credentials",
            "classification_type": "FR"
        }
    ],
    "project_context": "Test project"
}

try:
    print("Sending test case generation request...")
    response = requests.post(
        "http://localhost:8000/generate_test_cases",
        json=payload,
        timeout=120
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
