import os
import sys
import time
import json
import subprocess
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

def check_dependencies():
    """Check and install required dependencies"""
    required_packages = {
        'selenium': 'selenium',
        'yt-dlp': 'yt-dlp', 
        'webdriver-manager': 'webdriver-manager'
    }
    
    missing_packages = []
    
    for package, pip_name in required_packages.items():
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(pip_name)
    
    if missing_packages:
        print("Missing required packages:", ', '.join(missing_packages))
        install = input("Would you like to install them now? (y/n): ").lower()
        if install == 'y':
            for package in missing_packages:
                print(f"Installing {package}...")
                subprocess.run([sys.executable, '-m', 'pip', 'install', package])
        else:
            print("Please install the packages manually and run the script again.")
            sys.exit(1)

def setup_driver():
    """Setup Chrome WebDriver with options"""
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        print(f"Error setting up Chrome driver: {e}")
        print("Make sure Chrome browser is installed.")
        sys.exit(1)

def manual_login(driver):
    """Let user log in manually"""
    print("Opening TikTok login page...")
    driver.get("https://www.tiktok.com/login")
    
    print("\n" + "="*60)
    print("MANUAL LOGIN REQUIRED")
    print("="*60)
    print("1. Log into your TikTok account in the browser window")
    print("2. Complete any 2FA or captcha if required")
    print("3. Make sure you're fully logged in")
    print("4. Press Enter here when you're done logging in")
    print("="*60)
    
    input("Press Enter after you've successfully logged in...")
    
    # Verify login by checking for profile elements
    try:
        WebDriverWait(driver, 10).until(
            lambda d: "login" not in d.current_url.lower()
        )
        print("✓ Login successful!")
        return True
    except TimeoutException:
        print("⚠️  Login verification failed, but continuing anyway...")
        return True

def extract_bookmark_urls(driver):
    """Extract all bookmark URLs from TikTok"""
    print("\n" + "="*60)
    print("MANUAL NAVIGATION TO BOOKMARKS")
    print("="*60)
    print("1. Navigate to your TikTok bookmarks page in the browser")
    print("2. Make sure all your bookmarks are visible")
    print("3. Press Enter here when you're ready to start extraction")
    print("="*60)
    
    input("Press Enter when you're on your bookmarks page and ready...")
    
    print("Extracting bookmark URLs...")
    urls = set()
    last_count = 0
    scroll_attempts = 0
    max_scroll_attempts = 50
    
    while scroll_attempts < max_scroll_attempts:
        # Find video links using multiple selectors
        selectors = [
            "a[href*='/video/']",
            "a[href*='@'][href*='/video/']",
            "[data-e2e='bookmark-item'] a",
            ".video-feed-item a",
            "div[data-e2e] a[href*='/video/']",
            "a[href*='tiktok.com']"
        ]
        
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    href = element.get_attribute('href')
                    if href and '/video/' in href and 'tiktok.com' in href:
                        # Clean URL - remove any tracking parameters
                        clean_url = href.split('?')[0]
                        # Make sure it's a proper TikTok video URL
                        if '/video/' in clean_url:
                            urls.add(clean_url)
            except:
                continue
        
        current_count = len(urls)
        print(f"\rFound {current_count} bookmark URLs...", end="", flush=True)
        
        # Check if we found new URLs
        if current_count == last_count:
            scroll_attempts += 1
        else:
            scroll_attempts = 0
            last_count = current_count
        
        # Scroll down to load more content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Try different scroll methods
        try:
            # Scroll main content containers
            containers = driver.find_elements(By.CSS_SELECTOR, "[data-e2e='bookmark-list'], .bookmark-list, .video-feed")
            for container in containers:
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
        except:
            pass
        
        time.sleep(1)
    
    print(f"\n✓ Extraction complete! Found {len(urls)} unique bookmark URLs")
    return list(urls)

def save_urls_to_file(urls, filename="extracted_bookmarks.txt"):
    """Save URLs to a text file"""
    with open(filename, 'w', encoding='utf-8') as f:
        for url in urls:
            f.write(url + '\n')
    print(f"URLs saved to {filename}")
    
    # Debug: Show first few URLs
    print(f"\nDEBUG - First 5 URLs found:")
    for i, url in enumerate(list(urls)[:5]):
        print(f"  {i+1}. {url}")
    
    if len(urls) > 5:
        print(f"  ... and {len(urls) - 5} more")
    
    # Validate URLs
    valid_urls = []
    for url in urls:
        if '/video/' in url and 'tiktok.com' in url:
            valid_urls.append(url)
    
    print(f"\nURL Validation:")
    print(f"  Total URLs found: {len(urls)}")
    print(f"  Valid TikTok video URLs: {len(valid_urls)}")
    
    if len(valid_urls) != len(urls):
        print(f"  Invalid URLs filtered out: {len(urls) - len(valid_urls)}")
    
    return valid_urls

def download_video(url, output_dir, index, total):
    """Download a single TikTok video using yt-dlp"""
    print(f"\n[{index}/{total}] Downloading: {url}")
    
    cmd = [
        'yt-dlp',
        '--output', f'{output_dir}/%(uploader)s_%(title)s_%(id)s.%(ext)s',
        '--write-info-json',
        '--write-thumbnail', 
        '--embed-thumbnail',
        '--format', 'best[height<=1080]',
        '--no-warnings',
        '--no-playlist',
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(f"✓ Successfully downloaded")
            return True
        else:
            print(f"✗ Failed: {result.stderr.split(chr(10))[0]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ Download timed out")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("TikTok Automated Bookmarks Downloader")
    print("="*50)
    
    # Check dependencies
    check_dependencies()
    
    # Setup WebDriver
    driver = setup_driver()
    
    try:
        # Manual login
        if not manual_login(driver):
            print("Login failed. Exiting...")
            return
        
        # Extract bookmark URLs
        urls = extract_bookmark_urls(driver)
        
        if not urls:
            print("No bookmark URLs found. Make sure you have bookmarks and are on the correct page.")
            return
        
        # Save URLs to file for backup
        valid_urls = save_urls_to_file(urls)
        
        if not valid_urls:
            print("\nNo valid TikTok video URLs found!")
            print("This might happen if:")
            print("1. The page structure is different than expected")
            print("2. You're not on the bookmarks page")
            print("3. The bookmarks are loaded dynamically")
            print("\nTry scrolling more on the bookmarks page and run again.")
            return
        
        print(f"\nProceeding with {len(valid_urls)} valid URLs...")
        
        # Create output directory
        output_dir = "tiktok_bookmarks"
        Path(output_dir).mkdir(exist_ok=True)
        print(f"Downloading to: {os.path.abspath(output_dir)}")
        
        # Download videos
        successful = 0
        failed = 0
        
        print(f"\nStarting download of {len(valid_urls)} videos...")
        
        for i, url in enumerate(valid_urls, 1):
            if download_video(url, output_dir, i, len(urls)):
                successful += 1
            else:
                failed += 1
            
            # Small delay between downloads
            time.sleep(2)
        
        # Summary
        print(f"\n{'='*50}")
        print(f"DOWNLOAD SUMMARY")
        print(f"{'='*50}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Total: {len(urls)}")
        print(f"Downloads saved to: {os.path.abspath(output_dir)}")
        print(f"URLs backup saved to: extracted_bookmarks.txt")
        
    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user.")
        
    except Exception as e:
        print(f"\nError: {e}")
        
    finally:
        print("\nClosing browser...")
        driver.quit()

if __name__ == "__main__":
    main()
