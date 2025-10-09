import os
import pickle
import re
from functools import partial

import schedule
import yaml
from nicegui import app, run, ui

from pricechecker import Product, check_specials


def set_style(page):
    def wrap():
        ui.colors(primary="#5F5F5F")
        ui.add_head_html("""
        <meta name="theme-color" content="#f0f0f0">
        """)
        ui.add_body_html("""
        <style>
            body {
                background-color: #f0f0f0;
            }
            .q-field__inner {
                background-color: white;    
            }
            .q-tab-panels {
                background-color: #f0f0f0;
            }
            .q-tab {
                text-transform: none;
            }
        </style>
        """)
        page()

    return wrap


@ui.page("/")
@set_style
def index():
    def reset_view():
        make_cards.refresh("")
        specials_column.set_visibility(True)
        search.value = ""

    async def add_product(wid: int):
        p = Product(wid)

        with open("products.yaml", "r") as f:
            products = yaml.safe_load(f.read())

        if p.name not in products.keys():
            ui.notify("Product added!", type="positive", position="top")
            reset_view()

            products[p.name] = {"woolies": p.woolies.id, "coles": p.coles.id}

            with open("products.yaml", "w") as f:
                yaml.safe_dump(products, f)

            await run.cpu_bound(check_specials)
            current_specials.refresh()
        else:
            ui.notify("Product already tracked!", type="negative", position="top")
            reset_view()

    @ui.refreshable
    def make_cards(query):
        if query:
            specials_column.set_visibility(False)
            ui.run_javascript("document.activeElement.blur();")
            p = Product(query)
            with ui.row().classes("w-full justify-center min-w-[350px]"):
                with ui.card().tight().classes("aspect-square w-screen max-w-[600px]"):
                    with ui.image(p.woolies.image):
                        ui.label("Woolworths").classes(
                            "absolute-top text-subtitle2 text-center"
                        )
                    with ui.card_section():
                        ui.label(p.woolies.name)
                with ui.card().tight().classes("aspect-square w-screen max-w-[600px]"):
                    with ui.image(p.coles.image):
                        ui.label("Coles").classes(
                            "absolute-top text-subtitle2 text-center"
                        )
                    with ui.card_section():
                        ui.label(p.coles.name)
            with ui.row().classes("w-full justify-center"):
                ui.button(
                    icon="add",
                    text="Add Product",
                    on_click=partial(add_product, str(p.woolies.id)),
                ).props("color=green")

    def handle_key(e):
        if e.key == "Enter" and e.action.keydown:
            make_cards.refresh(search.value)

    def clear_cards(e):
        if e is None or e == "":
            reset_view()

    ui.keyboard(on_key=handle_key, ignore=[])

    with ui.column().classes("w-full items-center"):
        with ui.row().classes("w-full justify-center"):
            with (
                ui.input(on_change=lambda e: clear_cards(e.value))
                .props("outlined dense input-style='font-size: 16px;' clearable")
                .classes("w-screen max-w-[600px]") as search
            ):
                ui.button(
                    icon="search", on_click=lambda: make_cards.refresh(search.value)
                ).props("flat dense")
                ui.button(
                    icon="settings", on_click=lambda: ui.navigate.to("/config")
                ).props("flat dense")
        make_cards("")
        if os.path.exists("specials.pkl"):
            specials_column = current_specials()


@ui.page("/config")
@set_style
def config():
    def save_yaml(str):
        with open("products.yaml", "w") as f:
            f.write(str)

    with open("products.yaml", "r") as f:
        text = f.read()

    with ui.column().classes("w-full h-dvh items-center"):
        code = ui.codemirror(text, language="YAML", theme="monokai").classes(
            "h-[75vh] w-[90vw] max-w-[800px]"
        )
        with ui.row().classes("justify-end w-[90vw] max-w-[800px]"):
            ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props(
                "flat dense"
            )
            ui.button(icon="save", on_click=lambda: save_yaml(code.value)).props(
                "flat dense"
            )


@ui.refreshable
def current_specials():
    with open("specials.pkl", "rb") as f:
        specials = pickle.load(f)

    with ui.column().classes("items-center") as column:
        with ui.tabs().props("dense") as tabs:
            one = ui.tab("🍏 Woolies").classes("text-[#178841]")
            two = ui.tab("🍎 Coles").classes("text-[#e01a22]")
        with ui.tab_panels(tabs, value=one):
            with ui.tab_panel(one):
                make_specials_table(specials["woolies"])
            with ui.tab_panel(two):
                make_specials_table(specials["coles"])

    return column


def make_specials_table(specials):
    columns = [
        {
            "name": "product",
            "label": "Product",
            "field": "product",
            "align": "left",
        },
        {
            "name": "price",
            "label": "Price",
            "field": "price",
            "align": "left",
            "style": "width: 50px",
        },
        {
            "name": "discount",
            "label": "Save",
            "field": "discount",
            "align": "left",
            "style": "width: 50px",
        },
    ]
    rows = [
        {
            "product": re.sub(r"(?i) \d{1,}(?:ml|g|l|kg)", "", x[0]),
            "price": x[1],
            "discount": x[2],
        }
        for x in specials
    ]

    ui.table(columns=columns, rows=rows, row_key="name").props("dense").classes(
        "w-[90vw] max-w-[600px]"
    ).props("wrap-cells=true")


async def update_specials():
    await run.cpu_bound(check_specials)
    current_specials.refresh()


schedule.every().tuesday.at("18:00").do(update_specials)
ui.timer(60, schedule.run_pending)


for suffix in ["", "-precomposed", "-120x120-precomposed", "-120x120"]:
    app.add_static_file(
        local_file="logo.png", url_path=f"/apple-touch-icon{suffix}.png"
    )

if not os.path.exists("products.yaml"):
    open("products.yaml", "w+")

app.on_startup(update_specials)

ui.run(port=8888, title="Price Checker", favicon="🍎")
