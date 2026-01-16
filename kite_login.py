import os
import time
import hashlib
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from kiteconnect import KiteConnect

def setup_driver():
    """Set up Chrome driver with headless options"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def get_request_token(user_id, password, api_key, totp_code):
    """Automate Kite login and extract request token"""
    driver = setup_driver()
    
    try:
        # Navigate to Kite login page
        login_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
        print(f"Navigating to: {login_url}")
        driver.get(login_url)
        
        # Wait for and fill user ID
        user_id_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "userid"))
        )
        user_id_field.send_keys(user_id)
        print("User ID entered")
        
        # Fill password
        password_field = driver.find_element(By.ID, "password")
        password_field.send_keys(password)
        print("Password entered")
        
        # Click login button
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        print("Login button clicked")
        
        # Wait for TOTP page
        time.sleep(2)
        
        # Check if TOTP is required
        try:
            totp_field = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "totp"))
            )
            totp_field.send_keys(totp_code)
            print("TOTP entered")
            
            # Submit TOTP
            totp_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            totp_button.click()
            print("TOTP submitted")
        except:
            print("TOTP not required or already on redirect page")
        
        # Wait for redirect and extract request_token from URL
        WebDriverWait(driver, 10).until(
            lambda d: "request_token=" in d.current_url or "status=success" in d.current_url
        )
        
        current_url = driver.current_url
        print(f"Redirected to: {current_url}")
        
        # Extract request_token
        if "request_token=" in current_url:
            request_token = current_url.split("request_token=")[1].split("&")[0]
            print(f"Request token extracted: {request_token[:10]}...")
            return request_token
        else:
            raise Exception("Request token not found in redirect URL")
            
    except Exception as e:
        # Take screenshot on error
        os.makedirs("screenshots", exist_ok=True)
        driver.save_screenshot("screenshots/error.png")
        print(f"Error: {str(e)}")
        raise
    finally:
        driver.quit()

def generate_access_token(api_key, api_secret, request_token):
    """Generate access token using request token"""
    kite = KiteConnect(api_key=api_key)
    
    # Generate checksum
    checksum = hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode()).hexdigest()
    print(f"Checksum generated")
    
    # Generate session
    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        print(f"Access token generated: {access_token[:10]}...")
        return access_token
    except Exception as e:
        print(f"Error generating access token: {str(e)}")
        raise

def send_to_zoho(callback_url, access_token, api_key):
    """Send access token back to Zoho Creator"""
    try:
        payload = {
            "access_token": access_token,
            "api_key": api_key,
            "status": "success"
        }
        
        response = requests.post(callback_url, json=payload, timeout=30)
        print(f"Response sent to Zoho. Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending to Zoho: {str(e)}")
        # Try sending error status
        try:
            error_payload = {
                "status": "error",
                "error": str(e)
            }
            requests.post(callback_url, json=error_payload, timeout=30)
        except:
            pass
        raise

def main():
    """Main function"""
    # Get environment variables
    user_id = os.environ.get('KITE_USER_ID')
    password = os.environ.get('KITE_PASSWORD')
    api_key = os.environ.get('KITE_API_KEY')
    api_secret = os.environ.get('KITE_API_SECRET')
    totp_code = os.environ.get('KITE_TOTP')
    callback_url = os.environ.get('CALLBACK_URL')
    
    # Validate inputs
    if not all([user_id, password, api_key, api_secret, totp_code, callback_url]):
        raise ValueError("Missing required environment variables")
    
    print("Starting Kite login automation...")
    print(f"User ID: {user_id}")
    print(f"API Key: {api_key[:10]}...")
    
    # Step 1: Get request token
    request_token = get_request_token(user_id, password, api_key, totp_code)
    
    # Step 2: Generate access token
    access_token = generate_access_token(api_key, api_secret, request_token)
    
    # Step 3: Send back to Zoho
    success = send_to_zoho(callback_url, access_token, api_key)
    
    if success:
        print("✓ Successfully completed Kite login automation")
    else:
        raise Exception("Failed to send response to Zoho")

if __name__ == "__main__":
    main()
