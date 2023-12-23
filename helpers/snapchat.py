import aiohttp


class SnapChat:
    def __init__(self, username):
        self.username = username
        self.username_suggestions = ""

    async def fetch(self, session, url, method="GET", data=None, headers=None):
        async with session.request(method, url, data=data, headers=headers) as response:
            return await response.json(), response.status

    async def check_username(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:66.0) Gecko/20100101 Firefox/66.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://accounts.snapchat.com/",
            "Cookie": "xsrf_token=PlEcin8s5H600toD4Swngg; sc-cookies-accepted=true; web_client_id=b1e4a3c7-4a38-4c1a-9996-2c4f24f7f956; oauth_client_id=c2Nhbg==",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        }
        check_username_url = f"https://accounts.snapchat.com/accounts/get_username_suggestions?requested_username={self.username}&xsrf_token=PlEcin8s5H600toD4Swngg"

        async with aiohttp.ClientSession() as session:
            data, status = await self.fetch(
                session, check_username_url, "POST", headers=headers
            )

            if suggestions := data.get("reference", {}).get("suggestions", []):
                self.username_suggestions = suggestions

            return data.get("reference", {}).get("error_message", None)

    async def get_snapcode(self, bitmoji=False, size=None):
        filetype = "SVG" if bitmoji else "PNG"
        url = f"https://app.snapchat.com/web/deeplink/snapcode?username={self.username}&type={filetype}"

        if size and filetype == "PNG":
            if int(size) > 1000:
                raise ValueError("size can not exceed 1000")
            url += f"&size={size}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                snapcode = await response.read()

        return snapcode, filetype, f"{size}x{size}" if size else None
