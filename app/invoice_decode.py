import aiohttp
import typing
import pathlib

from models import Invoice, Item
import config


async def decode_qr(qr: typing.Union[pathlib.Path, str]):
    if isinstance(qr, str):
        return await _fetch_bill_query(qr)
    elif isinstance(qr, pathlib.Path):
        return await _fetch_bill_qr(qr)

async def _fetch_bill_query(query: str):
    
    async with aiohttp.ClientSession() as session:

        url = f'http://{config.BILL_FETCH_HOST}/bill/query'
        payload = {
            'query': query
        }

        async with session.post(url, json=payload) as res:

            return _convert_bill(await res.json())

async def _fetch_bill_qr(qr: pathlib.Path):

    async with aiohttp.ClientSession() as session:

        url = f'http://{config.BILL_FETCH_HOST}/bill/qr'
        files = {'file': open(qr, 'rb')}

        async with session.post(url, data=files) as res:

            return _convert_bill(await res.json())
    

def _convert_bill(bill):

    def convert_item(item):
        return {
            'total_price': item['price'] * item['quantity'],
            'name': item['name'],
            'details': '🤔'
        }

    return {
        'total_cost': bill['total'],
        'items': list(map(convert_item, bill['records']))
    }
