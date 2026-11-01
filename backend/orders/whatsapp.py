"""Every WhatsApp link in the system is built here from the ONE admin-managed number (StoreSettings.whatsapp_number)."""
from urllib.parse import quote

COUNTRY = '234'


def normalize_wa_number(raw):
    """'+234 808 831 7529' / '08088317529' / '+234 (0)808 831 7529' -> '2348088317529' (digits only, no local trunk 0)."""
    d = ''.join(c for c in str(raw or '') if c.isdigit())
    if d.startswith(COUNTRY + '0'):
        d = COUNTRY + d[len(COUNTRY) + 1:]
    elif d.startswith('0') and len(d) == 11:
        d = COUNTRY + d[1:]
    return d


def naira(amount, symbol='₦'):
    return f'{symbol}{amount:,.0f}' if amount == amount.to_integral_value() else f'{symbol}{amount:,.2f}'


def _url(number, text):
    n = normalize_wa_number(number)
    return f'https://wa.me/{n}?text={quote(text)}' if n else ''


def receipt_message(order, cfg):
    return (f'Hello {cfg.store_name}, I have made a bank transfer for order {order.reference} totaling {naira(order.total, cfg.currency_symbol)}. '
            'I have attached my payment receipt. Please verify my payment. Thank you.')


def build_whatsapp_url(order, cfg):
    """Customer -> business: send the payment receipt. '' if no number is configured."""
    return _url(cfg.whatsapp_number, receipt_message(order, cfg))


def build_support_url(order, cfg):
    """Customer -> business: help with a rejected / unclear payment."""
    return _url(cfg.whatsapp_number, f'Hello {cfg.store_name}, I need help with the payment for my order {order.reference} '
                                     f'({naira(order.total, cfg.currency_symbol)}). Thank you.')


def build_customer_url(order, cfg):
    """Admin -> customer chat (customer's own phone number, converted to international format)."""
    return _url(order.customer_phone, f'Hello {order.customer_name}, this is {cfg.store_name} regarding your order {order.reference}.')


def build_phone_url(phone, text):
    """Admin -> any customer by their phone number (converted to international format). '' if the number is unusable."""
    return _url(phone, text) if len(normalize_wa_number(phone)) >= 10 else ''
