import os
from dotenv import load_dotenv
import pandas as pd
import logging
import json
import requests
import datetime
from cryptography.hazmat.primitives.asymmetric import ed25519

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ApiTradingClient:
    secret_key = None
    api_key = None

    def __init__(self, secret_key: str, api_key: str):
        self.secret_key = secret_key
        self.api_key = api_key
        self.base_url = "https://coinswitch.co"
        self.headers = {
            "Content-Type": "application/json"
        }

    def call_api(self, url: str, method: str, headers: dict = None, payload: dict = {}):
        '''
        make an API call on webserver and return response
        '''
        final_headers = self.headers.copy()
        if headers is not None:
            final_headers.update(headers)

        response = requests.request(method, url, headers=headers, json=payload)
        # print("STATUS CODE", response.status_code) # Removed print for cleaner output
        if response.status_code == 429:
            logger.warning("Rate limiting encountered (429 Too Many Requests).")
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()

    def signatureMessage(self, method: str, url: str, payload: dict, epoch_time=""):
        '''
          Generate signature message to be signed for given request
        '''
        # message = method + url + json.dumps(payload, separators=(',', ':'), sort_keys=True)
        message = method + url + epoch_time
        return message

    def get_signature_of_request(self, secret_key: str, request_string: str) -> str:
        '''
          Returns the signature of the request
        '''
        try:
            request_string = bytes(request_string, 'utf-8')
            secret_key_bytes = bytes.fromhex(secret_key)
            secret_key = ed25519.Ed25519PrivateKey.from_private_bytes(secret_key_bytes)
            signature_bytes = secret_key.sign(request_string)
            signature = signature_bytes.hex()
        except ValueError:
            return False
        return signature

    def make_request(self, method: str, endpoint: str, payload: dict = {}, params: dict = {}):
        '''
        Make the request to :
          a. generate signature message
          b. generate signature signed by secret key
          c. send an API call with the encoded URL
        '''
        decoded_endpoint = endpoint
        if method == "GET" and len(params) != 0:
            endpoint += '?' + '&'.join([f"{key}={value}" for key, value in params.items()])
            # print("endpoint:", endpoint) # Removed print
            decoded_string = endpoint.replace('+', ' ')
            decoded_endpoint = requests.utils.unquote(decoded_string)
            # print("decoded_endpoint:", decoded_endpoint) # Removed print

        epoch_time = str(int(datetime.datetime.now().timestamp() * 1000))
        # print(epoch_time) # Removed print

        signature_msg = self.signatureMessage(method, decoded_endpoint, payload, epoch_time)
        # print("Signature msg:", signature_msg) # Removed print
        signature = self.get_signature_of_request(self.secret_key, signature_msg)
        if not signature:
            return {"message": "Please Enter Valid Keys"}
        # print("Signature is: ", signature) # Removed print
        headers = {
            "X-AUTH-SIGNATURE": signature,
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-EPOCH": epoch_time,
            "X-REQUEST-ID": "canary-app-abhi"+epoch_time
        }
        # print(headers) # Removed print

        url = f"{self.base_url}{endpoint}"
        # print(url) # Removed print
        
        response = self.call_api(url, method, headers=headers, payload=payload)
        return json.dumps(response, indent=4)

    def get_24h_all_pairs_data(self, params: dict = {}):
        return self.make_request("GET", "/trade/api/v2/futures/all-pairs/ticker", params=params)

    def futures_get_assets(self, params: dict = {}):
        return self.make_request("GET", "/trade/api/v2/futures/instrument_info", params=params)

def main():
    # --- Load the API keys from .env ---
    load_dotenv()
    api_key = os.getenv("API_KEY")
    secret_key = os.getenv("SECRET_KEY")

    if not api_key or not secret_key:
        logger.error("API_KEY and SECRET_KEY must be set in the .env file.")
        return # Exit if keys are missing

    # Initialize the API client
    api_client = ApiTradingClient(secret_key=secret_key, api_key=api_key)

    # --- Fetch 24-hour ticker data ---
    logger.info("Fetching 24-hour ticker data from CoinSwitch API...")
    ticker_data = None
    try:
        # The get_24h_all_pairs_data function returns a JSON string
        raw_response_str = api_client.get_24h_all_pairs_data(params={"exchange": "EXCHANGE_2"})
        
        # Load the JSON string into a Python dictionary
        ticker_data = json.loads(raw_response_str)
        
        if not ticker_data or not ticker_data.get('data'):
            logger.error(f"API response did not contain expected 'data' field: {ticker_data}")
            return # Exit if response is malformed
        
        # The actual ticker data is a dictionary under 'data', where keys are symbols.
        # We need to iterate over the values of this dictionary.
        ticker_map = ticker_data['data']
        ticker_list = []
        for symbol_key, details in ticker_map.items():
            # Add the symbol to the details dictionary for easier processing later
            details['symbol'] = symbol_key
            ticker_list.append(details)

        if not ticker_list:
            logger.warning("No ticker data found in the API response.")
            return # Exit if no data

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}", exc_info=True)
        return
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response from API: {e}", exc_info=True)
        return
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching ticker data: {e}", exc_info=True)
        return

    # --- Process and structure the retrieved data ---
    processed_data = []
    for ticker in ticker_list:
        try:
            # Extract required information and other relevant details
            processed_data.append({
                'Symbol': ticker.get('symbol'),
                'Average Price': ticker.get('index_price'), # Using index_price for Average Price
                'Low Price': ticker.get('low_price_24h'),
                'High Price': ticker.get('high_price_24h'),
                'Last Price': ticker.get('last_price'),
                'Exchange': ticker.get('exchange'),
                'Timestamp': ticker.get('timestamp'),
                'Best Ask Price': ticker.get('best_ask_price'),
                'Best Bid Price': ticker.get('best_bid_price'),
                'Price 24h Pcnt': ticker.get('price_24h_pcnt'),
                'Base Asset Volume 24h': ticker.get('base_asset_volume_24h'),
                'Quote Asset Volume 24h': ticker.get('quote_asset_volume_24h'),
                'Mark Price': ticker.get('mark_price'),
                'Open Interest': ticker.get('open_interest'),
                'Open Interest Value': ticker.get('open_interest_value'),
                'Funding Rate': ticker.get('funding_rate'),
                'Next Funding Timestamp': ticker.get('next_funding_timestamp'),
                'Best Bid Size': ticker.get('best_bid_size'),
                'Best Ask Size': ticker.get('best_ask_size'),
                
            })
        except Exception as e:
            logger.warning(f"Skipping malformed ticker entry: {ticker}. Error: {e}")
            continue

    if not processed_data:
        logger.warning("No valid data to export after processing.")
        return # Exit if no data after processing

    df = pd.DataFrame(processed_data)

    # --- Fetch Leverage Data ---
    logger.info("Fetching leverage data from CoinSwitch API...")
    leverage_df = pd.DataFrame()
    try:
        raw_leverage_response_str = api_client.futures_get_assets(params={"exchange": "EXCHANGE_2"})
        logger.info(f"Raw Leverage API Response: {raw_leverage_response_str}") # For debugging
        leverage_data = json.loads(raw_leverage_response_str)

        if not leverage_data or not leverage_data.get('data'):
            logger.warning(f"API response for leverage data did not contain expected 'data' field or was empty: {leverage_data}")
        else:
            instrument_map = leverage_data['data'] # This is the dictionary of instruments
            
            if not instrument_map:
                logger.warning("No instrument data found in the API response for leverage.")
            else:
                processed_leverage_data = []
                for symbol_key, instrument_details in instrument_map.items(): # Iterate over items to get symbol_key
                    processed_leverage_data.append({
                        'Symbol': symbol_key, # Use the key from the dictionary for the full symbol
                        'Base Asset': instrument_details.get('base_asset'),
                        'Quote Asset': instrument_details.get('quote_asset'),
                        'Status': instrument_details.get('status'),
                        'Instrument Type': instrument_details.get('type'), # Corrected key
                        'Min Leverage': instrument_details.get('min_leverage'), # Corrected key
                        'Max Leverage': instrument_details.get('max_leverage'), # Corrected key
                        'Leverage Step': instrument_details.get('leverage_step'),
                        'Min Base Quantity': instrument_details.get('min_base_quantity'),
                        'Base Quantity Step Size': instrument_details.get('base_quantity_step_size'),
                        'Lot Size': instrument_details.get('lot_size'),
                        'Quantity Precision': instrument_details.get('quantity_precision'),
                        'Price Precision': instrument_details.get('price_precision'),
                        'Tick Size': instrument_details.get('tick_size'),
                        'Max Market Base Quantity': instrument_details.get('max_market_base_quantity'),
                        'Max Base Quantity': instrument_details.get('max_base_quantity'),
                        'Risk Limit': instrument_details.get('risk_limit'),
                        'Maint Margin Rate': instrument_details.get('maint_margin_rate'), # Corrected key
                        'Taker Fee Rate': instrument_details.get('taker_fee_rate'),
                        'Maker Fee Rate': instrument_details.get('maker_fee_rate'),
                        'Liq Fee Rate': instrument_details.get('liq_fee_rate'),
                        'Quote Asset Precision': instrument_details.get('quote_asset_precision')
                    })
                leverage_df = pd.DataFrame(processed_leverage_data)
                leverage_df.set_index('Symbol', inplace=True)

    except requests.exceptions.RequestException as e:
        logger.error(f"API request for leverage data failed: {e}", exc_info=True)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response for leverage data: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching leverage data: {e}", exc_info=True)

    # Merge ticker_df with leverage_df
    if not leverage_df.empty:
        df = df.set_index('Symbol')
        df = df.merge(leverage_df, left_index=True, right_index=True, how='left', suffixes=('_ticker', '_leverage'))
        df.reset_index(inplace=True)

    # --- Export the processed data to a CSV file ---
    output_csv_file = "get_data_output.csv"
    try:
        df.to_csv(output_csv_file, index=False)
        logger.info(f"Successfully exported data to {output_csv_file}")
    except Exception as e:
        logger.error(f"Error exporting data to CSV: {e}", exc_info=True)

if __name__ == "__main__":
    main()
