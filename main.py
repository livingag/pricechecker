import os
import re
from datetime import date
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

            products[p.name] = {
                "woolies": {
                    "id": p.woolies.id,
                    "max_save": p.woolies.saving,
                    "price_history": [(str(date.today()), p.woolies.price)],
                },
                "coles": {
                    "id": p.coles.id,
                    "max_save": p.coles.saving,
                    "price_history": [(str(date.today()), p.coles.price)],
                },
            }

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
    async def remove_product(name: str):
        del products[name]
        with open("products.yaml", "w") as f:
            yaml.safe_dump(products, f)

        ui.navigate.to("/config")
        await run.cpu_bound(check_specials)
        current_specials.refresh()

    with open("products.yaml", "r") as f:
        products = yaml.safe_load(f)

    with ui.column().classes("w-full items-center"):
        with ui.card():
            with (
                ui.grid(columns="auto auto")
                .classes("items-center")
                .style("gap: 0.5rem")
            ):
                ui.markdown("**Product**")
                ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props(
                    "flat dense"
                )
                for product in products:
                    ui.label(product).classes("pr-4")
                    ui.button("❌", on_click=partial(remove_product, product)).props(
                        "flat dense"
                    )


def get_specials():
    with open("products.yaml", "r") as f:
        products = yaml.safe_load(f.read())

    specials = {"woolies": [], "coles": []}
    for name, product in products.items():
        for market in ["woolies", "coles"]:
            if product[market]["on_special"]:
                specials[market].append(
                    (
                        name,
                        f"${product[market]['price']:.2f}",
                        f"{product[market]['saving']:.0f}%",
                        product[market]["id"]
                    )
                )

    return specials


@ui.refreshable
def current_specials():
    specials = get_specials()

    with ui.column().classes("items-center") as column:
        with ui.tabs().props("dense") as tabs:
            one = ui.tab("🍏 Woolies").classes("text-[#178841]")
            two = ui.tab("🍎 Coles").classes("text-[#e01a22]")
        with ui.tab_panels(tabs, value=one):
            with ui.tab_panel(one):
                make_specials_grid(specials, "woolies")
            with ui.tab_panel(two):
                make_specials_grid(specials, "coles")

    return column


def make_specials_grid(specials: dict, supermarket: str):
    with (
        ui.card()
        .style("font-size: 13px;")
        .tight()
        .classes("p-2 w-[90vw] max-w-[600px]")
    ):
        with (
            ui.grid(columns="auto 50px 40px")
            .classes("items-center gap-0 w-full")
            .style("row-gap: 0.4rem")
        ):
            ui.label("Product").classes("border-b")
            ui.label("Price").classes("border-b")
            ui.label("Save").classes("border-b")

            for p in specials[supermarket]:
                ui.label(re.sub(r"(?i) \d{1,}(?:ml|g|l|kg)", "", p[0])).classes(
                    "pr-4"
                ).on("click", lambda p=p: product_image_dialog(p[3], supermarket))
                ui.label(p[1]).on(
                    "click", lambda p=p: price_chart_dialog(p[0], supermarket)
                )
                ui.label(p[2])


def product_image_dialog(name, market):
    product = Product(str(name), market=="coles")
    with ui.dialog() as dialog:
        ui.image(getattr(product, market).image)

    dialog.open()


def price_chart_dialog(name, market):
    with open("products.yaml", "r") as f:
        products = yaml.safe_load(f.read())
    product = products[name]
    price_history = product[market]["price_history"]

    with ui.dialog() as dialog:
        ui.echart(
            {
                "xAxis": {
                    "type": "category",
                    "splitLine": {"show": False},
                    "axisLine": {"show": False},
                    "axisTick": {"show": False},
                    "axisLabel": {"show": False},
                },
                "yAxis": {"type": "value", "axisLabel": {"formatter": "${value}"}},
                "series": [{"type": "line", "data": price_history}],
                "grid": {
                    "left": "50px",
                    "right": "10px",
                    "top": "10%",
                    "bottom": "10%",
                },
                "animation": False,
            },
            theme={
                "backgroundColor": "#ffffff",
            },
        )

    dialog.open()


async def update_specials():
    await run.cpu_bound(check_specials)
    current_specials.refresh()


schedule.every().wednesday.at("03:00").do(update_specials)
ui.timer(60, schedule.run_pending)


for suffix in ["", "-precomposed", "-120x120-precomposed", "-120x120"]:
    app.add_static_file(
        local_file="logo.png", url_path=f"/apple-touch-icon{suffix}.png"
    )

if not os.path.exists("products.yaml"):
    open("products.yaml", "w+")

app.on_startup(update_specials)
ui.add_css("page.css", shared=True)

ui.run(port=8888, title="Price Checker", favicon="🍎")
