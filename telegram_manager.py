import requests
import threading
import time
import os
import json

class TelegramManager:
    def __init__(self, token="8207649837:AAGUPfm6drZxbgNWfLN-Yp98T4yUtQZWyb4", chat_id="7069132483"):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}/"
        self.callbacks = {}
        self.last_update_id = 0
        
        # Start background polling
        self.polling_thread = threading.Thread(target=self._poll_updates, daemon=True)
        self.polling_thread.start()

    def send_message(self, text):
        url = self.api_url + "sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text
        }
        try:
            response = requests.post(url, json=payload)
            return response.json()
        except Exception as e:
            print(f"Error sending message: {e}")
            return None

    def send_photo_with_buttons(self, photo_path, caption):
        if not os.path.exists(photo_path):
            print(f"Photo path {photo_path} does not exist.")
            return None
            
        url = self.api_url + "sendPhoto"
        files = {"photo": open(photo_path, "rb")}
        
        # Inline Keyboard buttons
        reply_markup = {
            "inline_keyboard": [[
                {"text": "✅ I Know This Person", "callback_data": "allow_entry"},
                {"text": "❌ I Don't Know", "callback_data": "block_entry"}
            ]]
        }
        
        # Formatting payload for requests.post with files
        data = {
            "chat_id": self.chat_id,
            "caption": caption,
            "reply_markup": json.dumps(reply_markup)
        }

        try:
            response = requests.post(url, data=data, files=files)
            return response.json()
        except Exception as e:
            print(f"Error sending photo: {e}")
            return None

    def register_callback(self, key, function):
        self.callbacks[key] = function

    def _poll_updates(self):
        while True:
            url = self.api_url + f"getUpdates?offset={self.last_update_id + 1}&timeout=10"
            try:
                response = requests.get(url).json()
                if response.get("ok"):
                    for update in response.get("result", []):
                        self.last_update_id = update["update_id"]
                        
                        # Check for callback queries (button clicks)
                        if "callback_query" in update:
                            callback_data = update["callback_query"]["data"]
                            
                            # Get the name of the user who clicked the button
                            from_user = update["callback_query"].get("from", {})
                            user_name = from_user.get("first_name", "Admin")
                            
                            # Answer the callback query to remove the "loading" state on the button
                            self._answer_callback(update["callback_query"]["id"])
                            
                            if callback_data in self.callbacks:
                                # Trigger the registered function with the user's name
                                self.callbacks[callback_data](user_name)
                                
            except Exception as e:
                # Silently handle connection errors to avoid console spam
                # only print if it's a new or critical error
                pass
            
            time.sleep(5) # Wait longer between polls if there's an error or no updates

    def _answer_callback(self, callback_query_id):
        url = self.api_url + "answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        requests.post(url, json=payload)

# Example usage (if run directly)
if __name__ == "__main__":
    tm = TelegramManager()
    tm.send_message("Telegram Remote Management Module Started.")
    
    def on_allow():
        print("Remote Override: Access Allowed")
        tm.send_message("Access granted via remote override.")

    def on_block():
        print("Remote Override: Access Blocked")
        tm.send_message("Access denied via remote override.")

    tm.register_callback("allow_entry", on_allow)
    tm.register_callback("block_entry", on_block)
    
    print("Manager is running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
