import sys, time, argparse, uiautomator2 as UI
from pandas import Series, DataFrame, Timestamp
from numpy.random import uniform as rand
from loguru import logger as Log
from tqdm import tqdm

Log.remove()
Log._core.handlers.clear()
tformat = "HH:mm:ss.SSS"
LINE_FORMAT = "<level>[{time:%s} | {function} :: L{line}]</level> {message}"
Log.add(sys.stdout, format = LINE_FORMAT % tformat, colorize = True, backtrace = True)
FILE_FORMAT, tformat = "log/InstaAndroid_{time:YYYYMMDD-HHmm}.log", "YYYY/MM/DD " + tformat
Log.add(FILE_FORMAT, format = LINE_FORMAT % tformat, colorize = False, backtrace = True)

class InstaAndroid:

    # UI element selectors for Instagram Android app
    UI_SELECTORS = {
        'search_tab': {'description': 'Search and Explore'},
        'search_bar': {'resourceId': 'com.instagram.android:id/action_bar_search_edit_text'},
        'search_bar_alt': {'text': 'Search'},
        'accounts_tab': {'text': 'Accounts'},
        'user_result': {'className': 'android.widget.LinearLayout'},
        'following_button': {'text': 'Following'},
        'unfollow_button': {'text': 'Unfollow'},
        'confirm_unfollow': {'text': 'Unfollow'},
        'back_button': {'description': 'Back'}
    }

    COLUMNS_LIST = ["t_iter", "t_write", "t_find", "t_click", "t_conf", "t_done", "ok"]
    
    @property
    def rand(self): 
        return rand(self.delay_lower, self.delay_upper)

    def __init__(self, list_filename: str, delay_lower: int = 2, delay_upper: int = 8, device_ip: str = None):
        
        Log.info(f"Welcome. Reading follows from \"{list_filename}\"")
        with open(list_filename, "r") as file: 
            self.list = file.readlines()
        
        self.list = DataFrame(None, index = self.list, columns = self.COLUMNS_LIST)
        self.list.index = self.list.index.str.strip().rename("user").sort_values()
        verbose = f"Loaded {len(self.list)} follows from \"{list_filename}\":"
        Log.info(verbose + "\n" + self.list.to_string(max_rows = 20) + "\n")
        
        self.delay_lower, self.delay_upper = delay_lower, delay_upper
        
        # Connect to Android device
        try:
            if device_ip:
                self.device = UI.connect(device_ip)
            else:
                self.device = UI.connect()  # Connect to USB device
            Log.info(f"Connected to device: {self.device.info}")
        except Exception as e:
            Log.error(f"Failed to connect to device: {e}")
            raise

    def setup_instagram(self):
        """Launch Instagram and navigate to search"""
        Log.info("Launching Instagram app...")
        
        # Launch Instagram
        self.device.app_start("com.instagram.android")
        time.sleep(5)  # Give more time for app to load
        
        # Wait for app to fully load
        Log.info("Waiting for Instagram to load...")
        time.sleep(3)
        
        # Try multiple methods to get to search
        search_found = False
        
        # Method 1: Look for search tab with multiple selectors
        search_tab_selectors = [
            {'description': 'Search and Explore'},
            {'description': 'Search'},
            {'text': 'Search'},
            {'text': 'Search and Explore'},
            {'resourceId': 'com.instagram.android:id/search_tab'},
            {'className': 'android.widget.TextView', 'text': 'Search'},
            {'className': 'android.widget.TextView', 'text': 'Search and Explore'}
        ]
        
        for selector in search_tab_selectors:
            if self.device(**selector).exists(timeout=3):
                Log.info(f"Found search tab with selector: {selector}")
                self.device(**selector).click()
                search_found = True
                break
        
        # Method 2: Try clicking bottom navigation tabs (search is usually 2nd tab)
        if not search_found:
            Log.warning("Search tab not found, trying bottom navigation...")
            bottom_tab_positions = [
                (0.2, 0.95),  # Left side of bottom bar
                (0.4, 0.95),  # Second tab (usually search)
                (0.6, 0.95),  # Third tab
                (0.8, 0.95)   # Right side
            ]
            
            for x, y in bottom_tab_positions:
                Log.info(f"Trying to click at position ({x}, {y})")
                self.device.click(x, y)
                time.sleep(2)
                
                # Check if we're now in search by looking for search bar
                if self.device(text='Search').exists(timeout=2) or \
                   self.device(description='Search').exists(timeout=2):
                    Log.success("Successfully navigated to search via bottom navigation")
                    search_found = True
                    break
        
        # Method 3: Try using device back button and retry
        if not search_found:
            Log.warning("Trying to reset and find search...")
            self.device.press("back")
            time.sleep(1)
            self.device.press("home")
            time.sleep(1)
            self.device.app_start("com.instagram.android")
            time.sleep(5)
            
            # Try clicking the magnifying glass icon (common search icon)
            self.device.click(0.4, 0.95)  # Try second tab again
            time.sleep(2)
        
        if not search_found:
            Log.error("Could not navigate to search section")
            return False
            
        time.sleep(2)
        Log.success("Successfully navigated to search section")
        return True

    def switch_to_accounts_tab(self):
        """Switch from the default \"For you\" results tab to the \"Accounts\" tab.

        Instagram's redesigned search now lands on a \"For you\" tab full of
        suggested content. The real user results only appear under the
        \"Accounts\" tab, so we must click it before picking a search result.
        """
        Log.info('Switching to the "Accounts" tab...')

        # Instagram has changed the casing/wording of this tab over time, so
        # try several variants (the tab itself is a plain clickable label).
        accounts_selectors = [
            {'text': 'Accounts'},
            {'text': 'ACCOUNTS'},
            {'textContains': 'Accounts'},
            {'textContains': 'accounts'},
            {'description': 'Accounts'},
            {'descriptionContains': 'Accounts'},
        ]

        # Wait for the results tabs to render before looking for "Accounts".
        deadline = time.time() + 10
        while time.time() < deadline:
            for selector in accounts_selectors:
                tab = self.device(**selector)
                if tab.exists(timeout=1):
                    tab.click()
                    Log.success('Switched to the "Accounts" tab')
                    time.sleep(2)  # Wait for account results to load
                    return True
            time.sleep(0.5)

        Log.warning('Could not find the "Accounts" tab; continuing with the current tab')
        return False

    def search_user(self, username: str):
        """Search for a specific user"""
        Log.info(f"Searching for user: {username}")
        
        # Try multiple search bar selectors
        search_bar = None
        search_selectors = [
            {'resourceId': 'com.instagram.android:id/action_bar_search_edit_text'},
            {'text': 'Search'},
            {'description': 'Search'},
            {'className': 'android.widget.EditText'},
            {'textContains': 'Search'}
        ]
        
        for selector in search_selectors:
            if self.device(**selector).exists(timeout=3):
                search_bar = self.device(**selector)
                Log.info(f"Found search bar with selector: {selector}")
                break
        
        if not search_bar:
            Log.error("Could not find search bar")
            return False
            
        # Click search bar and clear any existing text
        search_bar.click()
        time.sleep(1)
        search_bar.clear_text()
        time.sleep(0.5)
        
        # Type username
        search_bar.set_text(username)
        Log.info(f"Typed username: {username}")
        time.sleep(3)  # Wait for search results to load

        # Instagram now defaults to a "For you" tab with suggested content, so
        # switch to the "Accounts" tab to get the actual user results.
        #self.switch_to_accounts_tab()

        # Click the second clickable element (first search result)
        Log.info("Looking for first search result...")
        
        # Wait a bit more for results to fully load
        time.sleep(2)

        ############################ list 1: suggestions
        
        # Get all clickable elements and click the second one (first search result)
        clickable_elements = self.device(clickable=True)

        if clickable_elements.exists(timeout=3):
            Log.info("Found clickable elements, clicking the second one (first search result)")
            # Get all clickable elements and click the second one
            all_clickables = self.device(clickable=True)
            if len(all_clickables) >= 2:
                all_clickables[0].click()  # Click the second clickable element
                time.sleep(2)
            else:
                Log.error("Not enough clickable elements found")
                return False
        else:
            Log.error(f"No clickable search results found for: {username}")
            return False

        ############################ list 2: "for you"

        clickable_elements = self.device(clickable=True)
        
        if clickable_elements.exists(timeout=3):
            Log.info("Found clickable elements, clicking the second one (first search result)")
            # Get all clickable elements and click the second one
            all_clickables = self.device(clickable=True)
            if len(all_clickables) >= 2:
                all_clickables[0].click()  # Click the second clickable element
                time.sleep(2)
                return True
            else:
                Log.error("Not enough clickable elements found")
                return False
        else:
            Log.error(f"No clickable search results found for: {username}")
            return False

        ############################

    def unfollow_user(self, username: str):
        """Unfollow the current user"""
        Log.info(f"Attempting to unfollow: {username}")
        
        # Look for "Following" button
        following_btn = self.device(**self.UI_SELECTORS['following_button'])
        if following_btn.exists(timeout=5):
            following_btn.click()
            time.sleep(1)
            
            # Look for "Unfollow" confirmation button
            unfollow_btn = self.device(**self.UI_SELECTORS['unfollow_button'])
            if unfollow_btn.exists(timeout=3):
                unfollow_btn.click()
                Log.info(f"Clicked unfollow button for: {username}")
                time.sleep(2)  # Wait for potential confirmation dialog
                
                # Check if a confirmation dialog appeared (for private accounts)
                # Look for confirmation dialog with multiple possible selectors
                confirmation_selectors = [
                    {'text': 'Unfollow'},
                    {'text': 'Confirm'},
                    {'text': 'Yes'},
                    {'text': 'Unfollow'},
                    {'description': 'Unfollow'},
                    {'description': 'Confirm'},
                    {'className': 'android.widget.Button', 'text': 'Unfollow'},
                    {'className': 'android.widget.Button', 'text': 'Confirm'}
                ]
                
                confirmation_clicked = False
                for selector in confirmation_selectors:
                    if self.device(**selector).exists(timeout=2):
                        Log.info(f"Found confirmation dialog with selector: {selector}")
                        self.device(**selector).click()
                        Log.success(f"Successfully unfollowed: {username} (with confirmation)")
                        confirmation_clicked = True
                        time.sleep(1)
                        break
                
                if not confirmation_clicked:
                    Log.success(f"Successfully unfollowed: {username} (no confirmation needed)")
                
                return True
            else:
                Log.error(f"Could not find unfollow confirmation for: {username}")
        else:
            Log.warning(f"User {username} may not be followed or profile not loaded")
        
        return False

    def go_back_to_search(self):
        """Navigate back to search"""
        # Try back button
        back_btn = self.device(**self.UI_SELECTORS['back_button'])
        if back_btn.exists(timeout=2):
            back_btn.click()
        else:
            # Use device back button
            self.device.press("back")
        time.sleep(1)
        
        # Go back to search again if needed
        self.device.press("back")
        time.sleep(1)

    def run(self):
        """Main execution function"""
        
        self.setup_instagram()
        iterator = tqdm(self.list.iterrows(), total = self.list.shape[0])
        Log.warning(f"Ready to start in {self.delay_upper} seconds...")
        
        time.sleep(self.delay_upper)
        self.list.loc[:, "ok"] = False

        for user, row in iterator:
            
            try:
                self.list.loc[user, "t_iter"] = Timestamp.utcnow()
                iterator.set_description(f"Processing \"{user}\"...")

                # Search for user
                time.sleep(self.rand)
                self.list.loc[user, "t_write"] = Timestamp.utcnow()
                
                if self.search_user(user):
                    self.list.loc[user, "t_find"] = Timestamp.utcnow()
                    
                    # Wait before unfollowing
                    time.sleep(self.rand)
                    iterator.set_description(f"Unfollowing \"{user}\"...")
                    self.list.loc[user, "t_click"] = Timestamp.utcnow()
                    
                    if self.unfollow_user(user):
                        self.list.loc[user, "t_conf"] = Timestamp.utcnow()
                        self.list.loc[user, "ok"] = True
                        Log.success(f"Done with \"{user}\". Moving on to the next user...")
                    else:
                        Log.error(f"Failed to unfollow: {user}")
                        self.list.loc[user, "ok"] = False
                else:
                    Log.error(f"Failed to find user: {user}")
                    self.list.loc[user, "ok"] = False

                self.list.loc[user, "t_done"] = Timestamp.utcnow()
                
                # Go back to search for next user
                self.go_back_to_search()
                time.sleep(self.rand)

            except KeyboardInterrupt: 
                Log.warning("Process stopped.")
                break
                
            except Exception as EXC:
                # Check if it's a device connection error
                if "device" in str(EXC) and "not found" in str(EXC):
                    Log.error(f"Device connection lost: {EXC}")
                    Log.error("Stopping process due to device connection error.")
                    break
                elif "AdbError" in str(type(EXC).__name__):
                    Log.error(f"ADB connection error: {EXC}")
                    Log.error("Stopping process due to ADB connection error.")
                    break
                else:
                    Log.exception(f"Error while processing \"{user}\": {EXC}")
                    self.list.loc[user, "ok"] = False
                    # Try to recover by going back to search
                    try:
                        self.go_back_to_search()
                    except:
                        pass

        # Save results
        ts = Timestamp.utcnow()
        filename = ts.strftime("./log/ig-unfollowed-android_%Y%m%d-%H%M.csv")
        self.list.to_csv(filename)
        Log.warning(f"Saved unfollows to \"{filename}\"")

###############################################################################################
###############################################################################################
###############################################################################################

if (__name__ == "__main__"):

    parser = argparse.ArgumentParser(description = "Unfollow users from Instagram on Android")
    parser.add_argument("list_filename", type = str, help = "Path to the list of users to unfollow")
    parser.add_argument("-dl", "--delay-lower", type = int, default = 0.1, help = "Lower delay in seconds")
    parser.add_argument("-du", "--delay-upper", type = int, default = 1.0, help = "Upper delay in seconds") 
    parser.add_argument("-d", "--device_ip", type = str, default = None, help = "Device IP for wireless connection")
    
    try: 
        InstaAndroid(**parser.parse_args().__dict__).run()
    except: 
        Log.exception("Unknown error")
