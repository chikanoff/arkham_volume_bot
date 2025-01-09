import csv
from chardet import detect

def detect_encoding(file_path, sample_size=4096):
    """Определение кодировки файла по первым байтам."""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(sample_size)
        result = detect(raw_data)
        encoding = result['encoding']
        return encoding
    except Exception as e:
        raise Exception(f"Ошибка определения кодировки файла {file_path}: {e}")

def load_account_info(file_path='accounts.csv'):
    """Загрузка информации из CSV файла."""
    accounts = []
    encoding = detect_encoding(file_path) or 'utf-8'

    with open(file_path, mode='r', encoding=encoding) as file:
        reader = csv.DictReader(file)
        for row in reader:
            api_key = row.get('api_key')
            api_secret = row.get('api_secret')
            proxy = row.get('proxy')
            is_perpetual = row.get('is_perpetual')
            leverage = row.get('leverage')
            accounts.append({
                'api_key': api_key,
                'api_secret': api_secret,
                'proxy': proxy,
                'is_perpetual': is_perpetual,
                'leverage': leverage
            })
    return accounts