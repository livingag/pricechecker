import datetime
import json
import re
from urllib.parse import quote

import requests
from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
}

COLES_API = ""


def after_next_wed(last_price: datetime.date) -> bool:
    diff = (datetime.date.today() - last_price).days
    days_to_next_wed = (2 - last_price.weekday() + 7) % 7
    if days_to_next_wed == 0:
        days_to_next_wed = 7

    return diff >= days_to_next_wed


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


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    woolies: Mapped["WooliesProduct"] = relationship(
        back_populates="product", lazy="joined", cascade="all, delete-orphan"
    )
    coles: Mapped["ColesProduct"] = relationship(
        back_populates="product", lazy="joined", cascade="all, delete-orphan"
    )

    def __init__(self, query: str):
        self.get_woolies(query)

    def get_woolies(self, query):
        self.woolies = WooliesProduct(search_woolies(query)[0])
        self.name = self.woolies.name
        self.get_coles(self.woolies.name)

    def get_coles(self, query):
        self.coles = ColesProduct(search_coles(query)[0])

    def update_prices(self):
        self.woolies.update_price()
        self.coles.update_price()


class StoreProduct:
    name: Mapped[str] = mapped_column(String)
    price: Mapped[int] = mapped_column(Integer)
    price_history: Mapped[str] = mapped_column(String)
    last_price: Mapped[datetime.date] = mapped_column(Date)
    special: Mapped[bool] = mapped_column(Boolean)
    image: Mapped[str] = mapped_column(String)
    saving: Mapped[int] = mapped_column(Integer)
    best_saving: Mapped[int] = mapped_column(Integer)
    store_id: Mapped[int] = mapped_column(Integer)

    def __init__(self, response):
        self.parse_json(response)

    def update_price(self):
        if after_next_wed(self.last_price):
            self.get_price()
            history = [int(x) for x in self.price_history.split(",")]
            history.append(self.price)
            self.price_history = ",".join([str(x) for x in history])


class WooliesProduct(StoreProduct, Base):
    __tablename__ = "woolies_products"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product: Mapped["Product"] = relationship(back_populates="woolies", lazy="joined")

    def parse_json(self, response):
        self.name = response["DisplayName"]

        if response["Price"] is not None:
            self.price = int(response["Price"] * 100)
        else:
            self.price = int(response["WasPrice"] * 100)

        self.price_history = str(self.price)
        self.last_price = datetime.date.today()
        self.store_id = response["Stockcode"]
        self.special = response["IsOnSpecial"]
        self.image = response["LargeImageFile"]

        if self.special:
            self.saving = int((response["SavingsAmount"] / response["WasPrice"]) * 100)
        else:
            self.saving = 0

        self.best_saving = self.saving

    def get_price(self):
        response = search_woolies(str(self.store_id))[0]

        if response["Price"] is not None:
            self.price = int(response["Price"] * 100)
        else:
            self.price = int(response["WasPrice"] * 100)

        self.special = response["IsOnSpecial"]

        if self.special:
            self.saving = int((response["SavingsAmount"] / response["WasPrice"]) * 100)
        else:
            self.saving = 0

        if self.saving > self.best_saving:
            self.best_saving = self.saving


class ColesProduct(StoreProduct, Base):
    __tablename__ = "coles_products"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product: Mapped["Product"] = relationship(back_populates="coles", lazy="joined")

    def parse_json(self, response):
        self.name = f"{response['brand']} {response['name']} {response['size']}"

        if response["pricing"]["now"] is not None:
            self.price = int(response["pricing"]["now"] * 100)
        else:
            self.price = int(response["pricing"]["was"] * 100)

        self.price_history = str(self.price)
        self.last_price = datetime.date.today()
        self.store_id = response["id"]
        self.image = f"https://cdn.productimages.coles.com.au/productimages{response['imageUris'][0]['uri']}"

        if response["pricing"]["was"] != 0:
            self.special = True
            self.saving = int(
                (response["pricing"]["saveAmount"] / response["pricing"]["was"]) * 100
            )
        else:
            self.special = False
            self.saving = 0

        self.best_saving = self.saving

    def get_price(self):
        response = get_coles_products([str(self.store_id)])[0]

        if response["pricing"]["now"] is not None:
            self.price = int(response["pricing"]["now"] * 100)
        else:
            self.price = int(response["pricing"]["was"] * 100)

        if response["pricing"]["was"] != 0:
            self.special = True
            self.saving = int(
                (response["pricing"]["saveAmount"] / response["pricing"]["was"]) * 100
            )
        else:
            self.special = False
            self.saving = 0

        if self.saving > self.best_saving:
            self.best_saving = self.saving
