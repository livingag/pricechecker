import json
import re
import smtplib
from urllib.parse import quote
from email.mime.text import MIMEText
from datetime import datetime

import requests
import yaml


HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
}

COLES_API = ""


class Product:
    def __init__(self, query: str, coles_id=False):
        if coles_id:
            self.get_coles_by_id(query)
        else:
            self.name = query
            self.get_woolies()
            self.get_coles()

    def get_woolies(self):
        self.woolies = WooliesProduct(search_woolies(self.name)[0])
        self.name = self.woolies.name

    def get_coles(self):
        self.coles = ColesProduct(search_coles(self.name)[0])
    
    def get_coles_by_id(self, coles_id):
        self.coles = ColesProduct(get_coles_products([coles_id])[0])


class WooliesProduct(Product):
    def __init__(self, response):
        self.parse_json(response)

    def parse_json(self, response):
        self.name = response["DisplayName"]
        self.price = response["Price"]
        self.id = response["Stockcode"]
        self.special = response["IsOnSpecial"]
        self.image = response["LargeImageFile"]

        if self.special:
            self.saving = (response["SavingsAmount"] / response["WasPrice"]) * 100
        else:
            self.saving = 0


class ColesProduct(Product):
    def __init__(self, response):
        self.parse_json(response)

    def parse_json(self, response):
        self.name = f"{response['brand']} {response['name']} {response['size']}"
        self.price = response["pricing"]["now"]
        self.id = response["id"]
        self.image = f"https://cdn.productimages.coles.com.au/productimages{response['imageUris'][0]['uri']}"

        if response["pricing"]["was"] != 0:
            self.special = True
            self.saving = (
                response["pricing"]["saveAmount"] / response["pricing"]["was"]
            ) * 100
        else:
            self.special = False
            self.saving = 0


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
    def after_next_wed(date_string: str) -> bool:
        date = datetime.strptime(date_string, "%Y-%m-%d")
        diff = (datetime.now() - date).days
        days_to_next_wed = (2 - date.weekday() + 7) % 7
        if days_to_next_wed == 0:
            days_to_next_wed = 7

        return diff >= days_to_next_wed

    def update_price_history(data):
        if not data["price_history"]:
            data["price_history"] = [(today, data["price"])]
        elif after_next_wed(data["price_history"][-1][0]):
            if len(data["price_history"]) == 10:
                data["price_history"] = data["price_history"][1:] + [
                    (today, data["price"])
                ]
            else:
                data["price_history"].append((today, data["price"]))

    with open("products.yaml", "r") as f:
        data = yaml.safe_load(f.read())

    today = str(datetime.now().date())

    woolies_ids = [
        str(v["woolies"]["id"]) for v in data.values() if v["woolies"]["id"] is not None
    ]
    coles_ids = [
        str(v["coles"]["id"]) for v in data.values() if v["coles"]["id"] is not None
    ]

    products = get_woolies_products(woolies_ids)
    for name, product in zip(data, products):
        woolies_data = data[name]["woolies"]
        woolies_data["price"] = product["Price"]
        woolies_data["on_special"] = product["IsOnSpecial"]

        if product["IsOnSpecial"]:
            woolies_data["saving"] = (
                product["SavingsAmount"] / product["WasPrice"]
            ) * 100
            if woolies_data["saving"] > woolies_data["max_save"]:
                woolies_data["max_save"] = woolies_data["saving"]

        update_price_history(woolies_data)

    products = get_coles_products(coles_ids)
    for name, product in zip(data, products):
        coles_data = data[name]["coles"]
        pricing = product["pricing"]
        coles_data["price"] = pricing["now"]
        if pricing["was"] != 0:
            coles_data["on_special"] = True
            coles_data["saving"] = (pricing["saveAmount"] / pricing["was"]) * 100
            if coles_data["saving"] > coles_data["max_save"]:
                coles_data["max_save"] = coles_data["saving"]
        else:
            coles_data["on_special"] = False
            coles_data["saving"] = 0

        update_price_history(coles_data)

    with open("products.yaml", "w") as f:
        yaml.safe_dump(data, f)
