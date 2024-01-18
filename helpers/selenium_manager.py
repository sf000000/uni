from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options


class SeleniumManager:
    def __init__(self, url: str = "https://www.google.com"):
        self.url = url

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--incognito")
        options.add_argument("--window-size=2560,1440")

        self.driver = webdriver.Firefox(options=options)

    def screenshot_element(self, element_id: str, file_name: str):
        self.driver.get(self.url)
        element = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, element_id))
        )
        element.screenshot(file_name)

        return file_name
