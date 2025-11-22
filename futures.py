
import datetime
import json
import requests
import os
from dotenv import load_dotenv
from cryptography.hazmat.primitives.asymmetric import ed25519

load_dotenv()

class ApiTradingClient:
    """
    Handles all communication with the cryptocurrency exchange's REST API.
    This class is responsible for signing requests and managing API calls.
    """
    def __init__(self, api_key: str, secret_key: str):
        """
        Initializes the API client with credentials.
        Args:
            api_key (str): The user's API key.
            secret_key (str): The user's secret key for signing requests.
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://coinswitch.co"
        self.headers = {
            "Content-Type": "application/json"
        }

    def _call_api(self, url: str, method: str, headers: dict = None, payload: dict = {}):
        """
        Private method to make a raw API call.
        It exists to centralize the request logic and handle potential rate limiting.
        """
        final_headers = self.headers.copy()
        if headers is not None:
            final_headers.update(headers)

        response = requests.request(method, url, headers=headers, json=payload)
        if response.status_code == 429:
            print("Rate limiting error encountered.")
        return response.json()

    def _signature_message(self, method: str, url: str, epoch_time: str, payload: dict = {}):
        """
        Generates the specific message string that needs to be signed.
        The exchange requires a precise concatenation of method, URL, and timestamp
        to validate the request's authenticity.
        """
        # The signature message must not contain any JSON payload.
        return method + url + epoch_time

    def _get_signature_of_request(self, request_string: str) -> str:
        """
        Signs the request string using the Ed25519 algorithm.
        This is the core of the authentication, proving the request originated
        from a user with the correct secret key.
        """
        try:
            request_bytes = bytes(request_string, 'utf-8')
            secret_key_bytes = bytes.fromhex(self.secret_key)
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(secret_key_bytes)
            signature_bytes = private_key.sign(request_bytes)
            return signature_bytes.hex()
        except ValueError:
            # This error occurs if the secret key is not a valid hex string.
            return ""

    def _make_request(self, method: str, endpoint: str, payload: dict = {}, params: dict = {}):
        """
        Orchestrates the entire process of sending a signed API request.
        This function brings together signature generation, header creation,
        and the final API call.
        """
        decoded_endpoint = endpoint
        if method == "GET" and params:
            # URL encodes parameters for GET requests.
            query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
            endpoint += '?' + query_string
            decoded_endpoint = requests.utils.unquote(endpoint.replace('+', ' '))

        epoch_time = str(int(datetime.datetime.now().timestamp() * 1000))

        # 1. Generate the message to be signed.
        signature_msg = self._signature_message(method, decoded_endpoint, epoch_time, payload)

        # 2. Sign the message with the secret key.
        signature = self._get_signature_of_request(signature_msg)
        if not signature:
            return {"error": "Invalid API Secret Key provided."}

        # 3. Construct the required authentication headers.
        headers = {
            "X-AUTH-SIGNATURE": signature,
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-EPOCH": epoch_time,
            "X-REQUEST-ID": f"gemini-bot-{epoch_time}"
        }

        url = f"{self.base_url}{endpoint}"
        
        # 4. Make the final API call.
        # 4. Make the final API call.
        response = self._call_api(url, method, headers=headers, payload=payload)
        return response

    def validate_keys(self):
        """
        Calls a dedicated endpoint to verify if the provided API keys are valid.
        This is a crucial first step to ensure the system can authenticate successfully.
        """
        return self._make_request("GET", "/trade/api/v2/validate/keys")

    def futures_wallet_balance(self, params: dict = {}):
        """
        Retrieves the wallet balance for the futures account.
        """
        return self._make_request("GET", "/trade/api/v2/futures/wallet_balance", params=params)

    def futures_update_leverage(self, payload: dict = {}):
        """
        Updates the leverage for a specific symbol.
        """
        return self._make_request("POST", "/trade/api/v2/futures/leverage", payload=payload)

    def futures_create_order(self, payload: dict = {}):
        """
        Creates a new futures order.
        """
        return self._make_request("POST", "/trade/api/v2/futures/order", payload=payload)

    def futures_get_order_by_id(self, params: dict = {}):
        """
        Retrieves the details of a specific order by its ID.
        """
        return self._make_request("GET", "/trade/api/v2/futures/order", params=params)

    def futures_cancel_order(self, payload: dict = {}):
        """
        Cancels an existing order.
        """
        return self._make_request("DELETE", "/trade/api/v2/futures/order", payload=payload)

# Example of how to instantiate and use the client.
# This part would typically be in main.py or another high-level module.
if __name__ == '__main__':
    api_key = os.getenv("API_KEY")
    secret_key = os.getenv("SECRET_KEY")

    if not api_key or not secret_key:
        print("Error: API_KEY and SECRET_KEY must be set in the .env file.")
    else:
        trading_client = ApiTradingClient(api_key=api_key, secret_key=secret_key)
        validation_response = trading_client.validate_keys()
        print("API Key Validation Response:")
        print(json.dumps(validation_response, indent=4))
