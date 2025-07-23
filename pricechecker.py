import requests
import json
import yaml
import smtplib
import configparser
from email.mime.text import MIMEText

config = configparser.ConfigParser()
config.read("config.ini")

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
}
GMAIL_ADDRESS = config.get("Gmail", "address")
GMAIL_PASSWORD = config.get("Gmail", "password")
PRODUCTS_URL = config.get("Products", "url")

WOOLIES_URL = "https://www.woolworths.com.au/apis/ui/products/"
COLES_URL = "https://www.coles.com.au/api/products"


def get_coles_products(product_ids):
    data = {"productIds": ",".join(product_ids)}

    r = requests.get(COLES_URL, headers=HEADERS, json=data)

    return json.loads(r.text)["results"]


def get_woolies_products(product_ids):
    r = requests.get(WOOLIES_URL + ",".join(product_ids), headers=HEADERS)

    return json.loads(r.text)


def send_email(subject, body, sender, recipients, password):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
        smtp_server.login(sender, password)
        smtp_server.sendmail(sender, recipients, msg.as_string())
    print("Email sent!")


response = requests.get(PRODUCTS_URL)
content = response.content.decode("utf-8")
product_ids = yaml.safe_load(content)

woolies_ids = [str(v["woolies"]) for v in product_ids.values() if v["woolies"] is not None]
coles_ids = [str(v["coles"]) for v in product_ids.values() if v["coles"] is not None]

products = get_woolies_products(woolies_ids)
woolies_specials = []
for product in products:
    if product["IsOnSpecial"]:
        saving = (product["SavingsAmount"] / product["WasPrice"]) * 100
        woolies_specials.append(f"{product['DisplayName']}: ${product['Price']:.2f} ({saving:.0f}% off)\n")
woolies_specials = "".join(sorted(woolies_specials))

products = get_coles_products(coles_ids)
coles_specials = []
for product in products:
    pricing = product["pricing"]
    if pricing["was"] != 0:
        name = f"{product['brand']} {product['name']} {product['size']}"
        saving = (pricing["saveAmount"] / pricing["was"]) * 100
        coles_specials.append(f"{name}: ${pricing['now']:.2f} ({saving:.0f}% off)\n")
coles_specials = "".join(sorted(coles_specials))

if len(woolies_specials + coles_specials) > 0:
    message_body = "Specials this week:\n\n"
    message_body += "Woolies:\n" + woolies_specials + "\n"
    message_body += "Coles:\n" + coles_specials
else:
    message_body = "No specials this week :("


subject = "Supermarket Specials This Week"
body = message_body

send_email(subject, body, GMAIL_ADDRESS, [GMAIL_ADDRESS], GMAIL_PASSWORD)
