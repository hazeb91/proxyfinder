"""Proxy Finder retrive proxies from different sources (trough plugins) and
check if they working on a determinate website.
"""

import time
import threading
import queue
import requests
import http.client

from . import plugins

PLUGINS = [
    plugins.FreeProxyListNet,
    plugins.HttpProxyScrapeCom,
    plugins.Socks4ProxyScrapeCom,
    plugins.Socks5ProxyScrapeCom,
]


def get_proxy_list():
    """Retrive a list of proxies from websites

    Returns:
        list: List of proxy info. Keys: ip, port, protocol.
    """
    proxy_list = []
    for plugin in PLUGINS:
        proxy_list.extend(plugin().scrape())
    # remove duplicate ip
    unique_proxies = list({v["ip"]:v for v in proxy_list}.values())
    return unique_proxies


def check_proxy(proxy, url, timeout=3.05):
    """Try connect proxy to url and check if it work

    Args:
        proxy (dict): Proxy info. Keys: ip, port, protocol.
        url (str): A website url
        timeout (float, optional): Max timeout for connection. Defaults to 3.05.

    Returns:
        dict: Modified proxy info adding connection error description
    """
    res = None
    error = ""
    with requests.Session() as s:
        s.proxies["http"] = "{protocol}://{ip}:{port}".format(**proxy)
        s.proxies["https"] = "{protocol}://{ip}:{port}".format(**proxy)

        try:
            res = s.get(url, verify=False, timeout=timeout)
        except requests.ConnectTimeout:
            error = "Request timed out while trying to connect"
        except requests.ReadTimeout:
            error = "Server did not send any data"
        except requests.TooManyRedirects:
            error = "Too many redirects"
        except requests.URLRequired:
            error = "Invalid URL"
        except requests.HTTPError:
            error = "HTTP error occurred"
        except requests.ConnectionError:
            error = "Connection error"
        except requests.RequestException:
            error = "Generic error"

        try:
            if res.status_code != 200:
                str_resp = http.client.responses[res.status_code]
                error = f"Error {res.status_code}: {str_resp}"
        except AttributeError:
            pass

        proxy["error"] = error
    return proxy


class SimplePrinter(threading.Thread):
    """Simple printer thread
    """

    def __init__(self, result_queue):
        super().__init__()

        self.result_queue = result_queue
        self._kill = False
        self.daemon = True

    def stop(self):
        """Stop printer thread
        """
        self._kill = True

    def run(self):
        """Printer start point
        """
        while not self._kill:
            line = self.result_queue.get()
            if not line["error"]:
                print("{protocol}://{ip}:{port}".format(**line))
            self.result_queue.task_done()


class Worker(threading.Thread):
    """Separate thread for process
    """

    def __init__(self, url, proxy_queue, result_queue, timeout):
        super().__init__()

        self.url = url
        self.proxy_queue = proxy_queue
        self.result_queue = result_queue
        self.timeout = timeout
        self._kill = False
        self.daemon = True

    def stop(self):
        """Stop current thread
        """
        self._kill = True

    def run(self):
        """Thread start point
        """
        while not self._kill:
            if self.proxy_queue.empty():
                return
            else:
                proxy = self.proxy_queue.get()
            res = check_proxy(proxy, self.url, self.timeout)
            self.result_queue.put(res)
            self.proxy_queue.task_done()


class ProxyFinder:
    """ProxyFinder Class
    """

    def __init__(self, url, max_proxies=-1, max_threads=20, conn_timeout=3.05):
        self.url = url
        self.max_proxies = max_proxies
        self.max_threads = max_threads
        self.conn_timeout = conn_timeout
        self.proxy_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.proxy_found = []
        self.all_results = []
        self.threads = []

    def get_proxies(self):
        """Retrive all proxies available in plugins

        Returns:
            list: All proxies found
        """
        proxy_list = get_proxy_list()
        if self.max_proxies > 0:
            self.proxy_found = proxy_list[:self.max_proxies]
        else:
            self.proxy_found = proxy_list
        return self.proxy_found

    def get_last_results(self):
        """Retrive last working proxies found

        Returns:
            list: Last working proxies found
        """
        last_results = []
        while not self.result_queue.empty():
            res = self.result_queue.get()
            last_results.append(res)
            self.result_queue.task_done()
        self.all_results.extend(last_results)
        return last_results

    def get_proxies_left(self):
        """Retrive number of proxies to process

        Returns:
            int: Number of proxies to process
        """
        return self.proxy_queue.qsize()

    def get_estimated_time(self):
        """Retrive estimated time to finish all processes

        Returns:
            str: Estimated time (hh:mm:ss)
        """
        est_secs = (self.proxy_queue.qsize() * self.conn_timeout) / self.max_threads
        return time.strftime('%H:%M:%S', time.gmtime(est_secs))

    def get_active_threads(self):
        """Retrive number of active threads

        Returns:
            int: Number of active threads
        """
        return sum(1 for t in self.threads if t.is_alive())

    def is_finished(self):
        """Check if all processes are finished

        Returns:
            bool: True if all processes are finished
        """
        for thread in self.threads:
            if thread.is_alive():
                return False
        return True

    def stop(self):
        """Stop all active threads and reset queues
        """
        for thread in self.threads:
            thread.stop()
        self.proxy_queue.queue.clear()
        self.result_queue.queue.clear()
        self.threads.clear()

    def start(self):
        """Start threads and processes
        """
        if not self.proxy_found:
            self.get_proxies()

        # Put proxies in queue
        for i, proxy in enumerate(self.proxy_found, 1):
            if i == self.max_proxies:
                break
            self.proxy_queue.put(proxy)

        # Create threads
        for _ in range(self.max_threads):
            t = Worker(self.url, self.proxy_queue, self.result_queue, self.conn_timeout)
            t.start()
            self.threads.append(t)


if __name__ == "__main__":
    pf = ProxyFinder("http://easybytez.com/", max_proxies=10)
    pf.start()

    pp = SimplePrinter(pf.result_queue)
    pp.start()

    while not pf.is_finished():
        time.sleep(1)

    pp.stop()
    pf.stop()
