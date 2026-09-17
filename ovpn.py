#!/usr/bin/python3.13
import httpx
import bs4
import asyncio
import sys
import os
import os.path
import aiofiles
import aiofiles.os
from urllib.parse import urlparse

cache = {
	"ip_geo": dict[str, dict[str, str | float | bool]](),
	"ips": list[str](),
}
headers = {
	"user-agent": "curl/8.11.1",
}

def geo_format(geo: dict[str, str | float | bool]) -> dict[str, str | float | bool]:
	geo["country"] = geo["country"].replace(' ', '_').lower()
	geo["regionName"] = geo["regionName"].replace(' ', '_').lower()
	geo["city"] = geo["city"].replace(' ', '_').lower()
	return geo

async def get_ip_geo(client: httpx.AsyncClient, ip: str, *, sleep: float = 10) -> dict[str, float | str | bool]:
	if ip in cache["ip_geo"].keys(): return cache["ip_geo"][ip]
	while True:
		try:
			response = await client.get(f"http://ip-api.com/json/{ip}")
			if response.status_code != 200: await asyncio.sleep(sleep)
			else: return response.json()
		except httpx.HTTPError:
			await asyncio.sleep(sleep)

async def download(client: httpx.AsyncClient, path: str, url: str):
	name = url.split('/')[-1]
	geo, file = await asyncio.gather(get_ip_geo(client, name.split('_')[0]), client.get(url))
	geo = geo_format(geo)
	path = path.format(country=geo["country"],region=geo["regionName"],city=geo["city"])
	await aiofiles.os.makedirs(path, exist_ok=True)
	async with aiofiles.open(path + os.sep + name, mode='w') as handle:
		await handle.write(file.text)

async def check(path: str, *queries: str):
	queries = {q.split('=')[0]: q.split('=')[1] for q in queries}
	country = queries.get("country")
	region = queries.get("region")
	city = queries.get("city")
	tasks = []
	async with httpx.AsyncClient(headers=headers) as client:
		for root, folder, files in os.walk(path):
			for file in files:
				ip = file.split('_')[0]
				if ip in cache["ips"]: continue 
				tasks += [get_ip_geo(client, ip)]
				cache["ips"] += [ip]
		geos = await asyncio.gather(*tasks)
	for geo in geos:
		geo = geo_format(geo)
		try:
			if country == geo["country"] or region == geo["regionName"] or city == geo["city"]:
				print(geo["query"])
		except KeyError: pass

async def get(url: str, path: str):
	url = urlparse(url)
	tasks = []
	async with httpx.AsyncClient(headers=headers) as client:
		page = await client.get(url.geturl())
		soup = bs4.BeautifulSoup(page.text, "lxml")
		for link in soup.find_all('a'):
			link = urlparse(link.get("href"))._replace(scheme = url.scheme, netloc = url.netloc)
			if link.path.endswith(".ovpn"): tasks += [download(client, path, link.geturl())]
		tasks = await asyncio.gather(*tasks)

if __name__ == "__main__":
	match sys.argv[1:]:
		case ["check", path, query, *queries]: asyncio.run(check(path, query, *queries))
		case ["get", url, path]: asyncio.run(get(url, path))
