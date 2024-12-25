# OVPN.py
A simple script to collect `.ovpn` files from your favorite website.

> [!NOTE]
> `{country}`, `{region}`, `{city}`, are python `format()` markers to be replaced with geolocatioon
> data into path when downloading the file.

Usage:
```console
$ ovpn.py get <url> <path[/{country}][/{region}][/{city}]>
$ ovpn.py check <path> <country|region|city=VALUE>+
```
