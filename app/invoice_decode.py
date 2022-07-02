from models import Invoice, Item


async def decode_qr(qr):
    def dummy(qr):
        invoice = {
            'total_cost': 2270,
            'items': [
                {
                    'total_price': 619,
                    'name': 'Пицца Чоризо',
                    'details': 'питца',
                },
                {
                    'total_price': 1402,
                    'name': 'Карбонара+',
                    'details': 'питца',
                },
                {
                    'total_price': 249,
                    'name': 'Песто',
                    'details': 'питца',
                },
            ],
        }
        return invoice

    return dummy(qr)
