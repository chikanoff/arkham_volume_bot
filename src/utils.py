import csv

def load_account_info(file_path='accounts.csv'):
    """Загрузка информации из CSV файла."""
    accounts = []
    with open(file_path, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            api_key = row.get('api_key')
            api_secret = row.get('api_secret')
            proxy = row.get('proxy')
            accounts.append({
                'api_key': api_key,
                'api_secret': api_secret,
                'proxy': proxy
            })
    return accounts