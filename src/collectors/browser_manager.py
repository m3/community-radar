from playwright.sync_api import sync_playwright

class PlaywrightManager:
    _instance = None

    def __init__(self):
        self.playwright = None
        self.browser = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self, headless=True):
        """Starts Playwright programmatically outside context managers."""
        if not self.playwright:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=headless)

    def get_context(self, proxy_cfg=None):
        """Provides an isolated browser context."""
        if not self.browser:
            self.start()
        return self.browser.new_context(proxy=proxy_cfg)

    def stop(self):
        """Clean teardown."""
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
        self.browser = None
        self.playwright = None
        PlaywrightManager._instance = None
