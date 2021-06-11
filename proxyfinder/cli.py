"""Console script for proxyfinder."""
import argparse
import sys

import pyperclip
from progressbar import ProgressBar

from . import proxyfinder


def p_format(proxy_info, show_error=False):
    """Return formatted text from a proxy info dictionary.

    Args:
        proxy_info (dict): Proxy dictionary info
        show_error (bool): A flag to show error. Default: False

    Returns:
        str: Formatted text
    """
    if show_error and proxy_info["error"]:
        return "{protocol}://{ip}:{port} -> {error}".format(**proxy_info)
    return "{protocol}://{ip}:{port}".format(**proxy_info)


def copy_to_clipboard(proxy_list):
    """Copy proxy addresses list to the clipboard.

    Args:
        proxy_list (list): List of proxy addresses
    """
    joined = "\n".join(p_format(proxy) for proxy in proxy_list)
    pyperclip.copy(joined)


def list_only(proxy_list, output=None):
    """Show proxy addresses and save on file if is passed as argument.

    Args:
        proxy_list (list): List of proxy addresses
        output (TextIO, optional): File-like object to write. Defaults to None.
    """
    joined = "\n".join(p_format(proxy) for proxy in proxy_list)
    print(joined)
    if output:
        output.write(joined)


def main():
    """Console script for proxyfinder."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--url", type=str, help="A valid URL to check proxy addresses.")
    parser.add_argument("-p", "--max-proxies", type=int, default=0, help="Max number of proxy addresses to check. Set 0 to check all. (default: 0)")
    parser.add_argument("-t", "--max-threads", type=int, default=20, help="Max number of connections at the same time. (default: 20)")
    parser.add_argument("-n", "--conn-timeout", type=float, default=3.05, help="Max time (in seconds) to wait to establish a connection. (default: 3.05)")
    parser.add_argument("-a", "--show-all", action="store_true", help="Show all online/offline proxy addresses.")
    parser.add_argument("-c", "--copy", action="store_true", help="Copy proxy addresses to the clipboard.")
    parser.add_argument("-l", "--proxy-list", action="store_true", help="Show proxy addresses only. You can use this with --output-file to save proxy addresses.")
    parser.add_argument("-o", "--output-file", type=argparse.FileType("w"), help="Write proxy addresses to a file.")
    args = parser.parse_args()

    # if is not a list request than URL is necessary
    if not args.proxy_list and args.url is None:
        parser.print_help()
        print("\nYou must provide a valid URL.")
        sys.exit()

    if args.proxy_list:
        proxy_list = proxyfinder.get_proxy_list()
        list_only(proxy_list, args.output_file)
        if args.copy:
            copy_to_clipboard(proxy_list)
        sys.exit()

    # Prepare to check proxy addresses
    pf = proxyfinder.ProxyFinder(url=args.url, max_proxies=args.max_proxies,
        max_threads=args.max_threads, conn_timeout=args.conn_timeout)
    pf.start()

    working = []

    with ProgressBar(max_value=len(pf.get_proxies()), redirect_stdout=True) as bar:
        while not pf.is_finished() or not pf.result_queue.empty():
            try:
                last_results = pf.get_last_results()
                for res in last_results:
                    if not res["error"]:
                        working.append(res)
                    if not args.show_all and res["error"]:
                        continue
                    print(p_format(res, show_error=True))

                # update progress bar
                progress = len(pf.proxy_found) - pf.get_proxies_left()
                bar.update(progress - 1)
            except KeyboardInterrupt:
                pf.stop()
                break
        bar.update(len(pf.proxy_found))

    # last tasks
    if args.copy:
        copy_to_clipboard(working)
    if args.output_file:
        args.output_file.write("\n".join(p_format(proxy) for proxy in working))

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
