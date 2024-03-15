import requests
from pprint import pprint

url = 'https://dictionary.yandex.net/api/v1/dicservice.json/lookup'

def translate_word(word, token, lang='ru-en'):
    ya_params = {
        'key': token,
        'lang': lang,
        'text': word
    }
    response = requests.get(url, params=ya_params).json()
    # pprint(response)
    trans_word = response['def'][0]['tr'][0]['text']
    return trans_word

if __name__ == '__main__':
    print(translate_word('собака'))