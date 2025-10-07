import json
import pickle
import re
import smtplib
from urllib.parse import quote
from email.mime.text import MIMEText

import requests
import yaml


HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
}

COLES_API = ""


class Product:
    def __init__(self, name: str):
        self.name = name
        self.get_woolies()

    def get_woolies(self):
        self.woolies = WooliesProduct(search_woolies(self.name)[0])
        self.name = self.woolies.name
        self.get_coles()

    def get_coles(self):
        self.coles = ColesProduct(search_coles(self.name)[0])


class WooliesProduct(Product):
    def __init__(self, json):
        self.parse_json(json)

    def parse_json(self, json):
        self.name = json["DisplayName"]
        self.price = json["Price"]
        self.id = json["Stockcode"]
        self.special = json["IsOnSpecial"]
        self.image = json["LargeImageFile"]


class ColesProduct(Product):
    def __init__(self, json):
        self.parse_json(json)

    def parse_json(self, json):
        self.name = f"{json['brand']} {json['name']} {json['size']}"
        self.price = json["pricing"]["now"]
        self.id = json["id"]
        self.image = f"https://cdn.productimages.coles.com.au/productimages{json['imageUris'][0]['uri']}"

        if json["pricing"]["was"] != 0:
            self.special = True
        else:
            self.special = False


def search_woolies(query: str) -> list:
    url = "https://www.woolworths.com.au/apis/ui/Search/products"
    r = requests.get(url + f"?searchTerm={quote(query)}", headers=HEADERS)
    p = [x["Products"][0] for x in json.loads(r.content)["Products"]]
    return [x for x in p if not x["IsMarketProduct"]]


def search_coles(query: str) -> list:
    global COLES_API
    url = f"https://www.coles.com.au/_next/data/{COLES_API}/en/search/products.json"
    r = requests.get(url + f"?q={quote(query)}", headers=HEADERS)

    try:
        results = json.loads(r.content)["pageProps"]["searchResults"]["results"]
    except json.JSONDecodeError:
        COLES_API = re.findall(r"\"buildId\":\"([^,]*)\"", r.text)[0]
        results = search_coles(query)

    return results


def get_coles_products(product_ids):
    data = {"productIds": ",".join(product_ids)}

    r = requests.get(
        "https://www.coles.com.au/api/products", headers=HEADERS, json=data
    )

    return json.loads(r.text)["results"]


def get_woolies_products(product_ids):
    r = requests.get(
        "https://www.woolworths.com.au/apis/ui/products/" + ",".join(product_ids),
        headers=HEADERS,
    )

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


def check_specials():
    with open("products.yaml", "r") as f:
        product_ids = yaml.safe_load(f.read())

    woolies_ids = [
        str(v["woolies"]) for v in product_ids.values() if v["woolies"] is not None
    ]
    coles_ids = [
        str(v["coles"]) for v in product_ids.values() if v["coles"] is not None
    ]

    products = get_woolies_products(woolies_ids)
    woolies_specials = []
    for product in products:
        if product["IsOnSpecial"]:
            saving = (product["SavingsAmount"] / product["WasPrice"]) * 100
            woolies_specials.append(
                (
                    f"{product['DisplayName']}",
                    f"${product['Price']:.2f} ({saving:.0f}% off)",
                )
            )

    products = get_coles_products(coles_ids)
    coles_specials = []
    for product in products:
        pricing = product["pricing"]
        if pricing["was"] != 0:
            name = f"{product['brand']} {product['name']} {product['size']}"
            saving = (pricing["saveAmount"] / pricing["was"]) * 100
            coles_specials.append(
                (f"{name}", f"${pricing['now']:.2f} ({saving:.0f}% off)")
            )

    specials = {"woolies": woolies_specials, "coles": coles_specials}

    with open("specials.pkl", "wb") as f:
        pickle.dump(specials, f)
