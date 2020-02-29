import requests
import json
from src.config.config import *


def _catfact(username=config['username']):
	url = 'https://catfact.ninja/facts'
	params = dict(language='en')

	data = requests.get(url=url, params=params)
	binary = data.content
	result = json.loads(binary)

	fact = result['data'][0]['fact']

	return f'@{username} did you know: {fact}'
