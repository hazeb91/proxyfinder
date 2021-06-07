from bs4 import BeautifulSoup
import requests


class PluginBase:
    """Plugin base class
    """

    HOST = None

    def __init__(self):
        self.response = None

    def get_data(self):
        pass

    def get_request(self):
        self.response = requests.get(self.HOST)

    def scrape(self):
        self.get_request()
        return self.get_data()


class FreeProxyListNet(PluginBase):

    HOST = "https://free-proxy-list.net/"

    def get_data(self):
        soup = BeautifulSoup(self.response.content, "html.parser")
        table = soup.find("table")
        rows = table.find_all("tr")
        head = ("ip", "port", "code", "country", "anonymity", "google", "https", "last_check")
        for row in rows:
            td = row.find_all("td")
            if td:
                ip = td[0].text
                port = int(td[1].text)
                protocol = "https" if td[6].text == "yes" else "http"
                yield {"protocol": protocol, "ip": ip, "port": port}


class ProxyScrapeComBase(PluginBase):

    PROTOCOL = None

    def get_data(self):
        for line in self.response.text.split("\r\n"):
            if line:
                ip, port = line.split(":")
                yield {"protocol": self.PROTOCOL, "ip": ip, "port": int(port)}


class HttpProxyScrapeCom(ProxyScrapeComBase):

    HOST = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"
    PROTOCOL = "http"


class Socks4ProxyScrapeCom(ProxyScrapeComBase):

    HOST = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all"
    PROTOCOL = "socks4"


class Socks5ProxyScrapeCom(ProxyScrapeComBase):

    HOST = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all"
    PROTOCOL = "socks5"


if __name__ == "__main__":
    # print(*FreeProxyListNet().scrape(), sep="\n")
    print(*HttpProxyScrapeCom().scrape(), sep="\n")
