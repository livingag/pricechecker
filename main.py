import schedule
import yaml
from nicegui import ui

from pricechecker import Product, check_specials


@ui.page("/")
def index():
    def handle_key(e):
        if e.key == "Enter" and e.action.keydown:
            make_cards.refresh(search.value)

    ui.colors(primary="#5F5F5F")
    ui.keyboard(on_key=handle_key, ignore=[])
    with ui.column().classes("w-full items-center"):
        with ui.row().classes("w-full justify-center"):
            with (
                ui.input()
                .props("outlined dense")
                .classes("w-1/4 min-w-[400px]") as search
            ):
                ui.button(
                    icon="search", on_click=lambda: make_cards.refresh(search.value)
                ).props("flat dense")
                ui.button(
                    icon="settings", on_click=lambda: ui.navigate.to("/config")
                ).props("flat dense")
        make_cards("")


@ui.page("/config")
def config():
    ui.colors(primary="#5F5F5F")

    def save_yaml(str):
        with open("products.yaml", "w") as f:
            f.write(str)

    with open("products.yaml", "r") as f:
        text = f.read()

    with ui.column().classes("w-full h-dvh items-center"):
        code = ui.codemirror(text, language="YAML", theme="monokai").classes(
            "w-2/6 h-3/4 min-w-[400px]"
        )
        with ui.row().classes("w-2/6 justify-end min-w-[400px]"):
            ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props(
                "flat dense"
            )
            ui.button(icon="save", on_click=lambda: save_yaml(code.value)).props(
                "flat dense"
            )


def add_product(wid: int):
    p = Product(wid)

    with open("products.yaml", "r") as f:
        products = yaml.safe_load(f.read())

    if p.name not in products.keys():
        products[p.name] = {"woolies": p.woolies.id, "coles": p.coles.id}

        with open("products.yaml", "w") as f:
            yaml.safe_dump(products, f)

        ui.notify("Product added!", type="positive", position="top")
    else:
        ui.notify("Product already tracked!", type="negative", position="top")


@ui.refreshable
def make_cards(query):
    if query:
        p = Product(query)
        with ui.row().classes("w-full justify-center min-w-[400px]"):
            with ui.card().tight().classes("aspect-square w-1/4 min-w-[400px]"):
                with ui.image(p.woolies.image):
                    ui.label("Woolworths").classes(
                        "absolute-top text-subtitle2 text-center"
                    )
                with ui.card_section():
                    ui.label(p.woolies.name)
            with ui.card().tight().classes("aspect-square w-1/4 min-w-[400px]"):
                with ui.image(p.coles.image):
                    ui.label("Coles").classes("absolute-top text-subtitle2 text-center")
                with ui.card_section():
                    ui.label(p.coles.name)
        with ui.row().classes("w-full justify-center"):
            ui.button(
                icon="add",
                text="Add Product",
                on_click=lambda: add_product(p.woolies.id),
            )


schedule.every().tuesday.at("23:00").do(check_specials)
ui.timer(0.1, schedule.run_pending)

ui.run(port=8888, title="Price Checker", favicon="🍎")
