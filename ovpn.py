#!/usr/bin/python3.13
import httpx
import bs4
import asyncio
import random
import sys
import os
import os.path
import aiofiles
import aiofiles.os
from urllib.parse import urlparse, ParseResult, ParseResultBytes

class cache:
	geos: dict[str, dict[str, str | float | bool]] = {}
	urls: list[ParseResult] = []
	ips: list[str] = []

def genheaders() -> dict[str, str]:
	return {
		"user-agent": f"Firefox/{random.randint(100, 200)}",
	}

def urlformat(url: str, current: ParseResult = None) -> ParseResult:
	url = urlparse(url)
	if url.__class__ == ParseResultBytes: url = url.decode()
	url = url._replace(scheme=current.scheme, netloc=current.netloc)
	if url.path == "": url = url._replace(path=current.path)
	return url

def geoformat(geo: dict[str, str | float | bool]) -> dict[str, str | float | bool]:
	geo["country"] = geo["country"].replace(' ', '_').lower()
	geo["region"] = geo["regionName"].replace(' ', '_').lower()
	geo["city"] = geo["city"].replace(' ', '_').lower()
	return geo

def matches(geo: dict[str, str | float | bool], queries: dict[str, str | float | bool]) -> bool:
	for k, _ in zip(queries.keys(), geo.keys()):
		if queries[k] != geo[k]: return False
	return True

def getvpndata(file: str) -> tuple[str, str, int]:
	tokens = [l.replace('\r', '').split(' ') for l in file.split('\n')]
	ip, proto, port = None, None, None
	for line in tokens:
		if line[0] == "proto": proto = line[1]
		elif line[0] == "remote": ip, port = line[1], int(line[2])
	return ip, proto, port

async def getgeo(client: httpx.AsyncClient, ip: str, *, api: str = "http://ip-api.com/json/{}", delay: float = 10) -> dict[str, str | float | bool]:
	if ip in cache.geos: return cache.geos[ip]
	data = None
	while not data:
		try:
			response = await client.get(api.format(ip))
			if response.status_code != 200: await asyncio.sleep(delay)
			else: data = cache.geos[ip] = response.json()
		except httpx.HTTPError:
			await asyncio.sleep(delay)
	return cache.geos[ip]

async def scan(client: httpx.AsyncClient, url: ParseResult) -> list[ParseResult]:
	if url in cache.urls: return []
	cache.urls += [url]
	global scan
	scans = []
	files = []
	try:
		page = await client.get(url.geturl())
	except httpx.HTTPError:
		return []
	if not page.headers["content-type"].startswith("text/html"):
		return []
	soup = bs4.BeautifulSoup(page.text, "lxml")
	for link in soup.find_all('a'):
		link = urlformat(link.get("href"), url)
		if link in cache.urls or link.netloc != url.netloc: continue
		if link.path.endswith(".ovpn"):
			cache.urls += [link]
			files += [link]
		else: scans += [scan(client, link)]
	for scanned in await asyncio.gather(*scans):
		files += scanned
	return files

async def download(client: httpx.AsyncClient, url: ParseResult, path: str, *, delay: float = 10) -> None:
	handle = None
	while not handle:
		try:
			file = await client.get(url.geturl())
			if file.status_code != 200: return
			ip, proto, port = getvpndata(file.text)
			geo = await getgeo(client, ip)
			cache.geos[ip] = geo = geoformat(geo)
			path = path.format(country=geo["country"], region=geo["region"], city=geo["city"])
			name = f"{ip}_{proto}_{port}.ovpn"
			await aiofiles.os.makedirs(path, exist_ok=True)
			async with aiofiles.open(path + os.sep + name, mode='wb') as handle:
				await handle.write(file.content)
		except httpx.HTTPError:
			await asyncio.sleep(delay)

async def get(url: str, path: str) -> None:
	url = urlparse(url)
	tasks = []
	async with httpx.AsyncClient(headers=genheaders(), timeout=300) as client:
		servers = await scan(client, url)
		for server in servers:
			tasks += [download(client, server, path)]
		await asyncio.gather(*tasks)

async def check(path: str, *queries: str) -> None:
	queries = {s[0]: s[1] for q in queries if (s := q.split('='))}
	geos = []
	async with httpx.AsyncClient(headers=genheaders(), timeout=60) as client:
		for root, folder, files in os.walk(path):
			for file in files:
				ip = file.split('_')[-3]
				if ip in cache.ips: continue
				geos += [getgeo(client, ip)]
				cache.ips += [ip]
		geos = await asyncio.gather(*geos)
	for geo in geos:
		if matches(geoformat(geo), queries):
			print(geo["query"])

if __name__ == "__main__":
	match sys.argv[1:]:
		case ["get", url, path]: asyncio.run(get(url, path))
		case ["check", path, *queries]: asyncio.run(check(path, *queries))
