import os
import re
from functools import partial

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from nicegui import app, ui
from sqladmin import Admin, ModelView
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models import Base, ColesProduct, Product, WooliesProduct

DATABASE_URL = "sqlite+aiosqlite:///products.db"  # Update with your DB URL
async_engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(
    async_engine, expire_on_commit=False, class_=AsyncSession
)


async def init_db() -> None:
    # Create the database tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


app.on_startup(init_db)


def set_style(page):
    async def wrap():
        ui.colors(primary="#5F5F5F")
        ui.add_head_html("""
        <meta name="theme-color" content="#f0f0f0">
        """)
        await page()

    return wrap


@ui.page("/")
@set_style
async def index():
    def reset_view():
        make_cards.refresh("")
        specials_column.set_visibility(True)
        search.value = ""

    async def add_product(wid: int):
        p = Product(wid)

        async with async_session() as session:
            result = await session.execute(
                select(Product).where(Product.name == p.name)
            )

        if len(result.all()) == 0:
            ui.notify("Product added!", type="positive", position="top")
            reset_view()

            async with async_session() as session:
                session.add(p)
                await session.commit()

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
                    on_click=partial(add_product, str(p.woolies.store_id)),
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
        specials_column = await current_specials()


@ui.page("/config")
@set_style
async def config():
    async def remove_product(product: Product, session):
        await session.delete(product)
        await session.commit()
        ui.navigate.to("/config")
        current_specials.refresh()

    async with async_session() as session:
        count = await session.scalars(select(func.count()).select_from(Product))

        if count.first() == 0:
            ui.notify("No products tracked!", type="warning", position="top")
            ui.navigate.to("/")

        products = await session.scalars(select(Product).order_by(Product.name))

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
                        ui.label(product.name).classes("pr-4")
                        ui.button(
                            "❌", on_click=partial(remove_product, product, session)
                        ).props("flat dense")


async def get_specials(session):
    products = await session.scalars(select(Product))
    if len(products.all()) == 0:
        return None

    woolies_specials = await session.scalars(
        select(WooliesProduct)
        .where(WooliesProduct.special == 1)
        .order_by(WooliesProduct.name)
    )
    coles_specials = await session.scalars(
        select(ColesProduct)
        .where(ColesProduct.special == 1)
        .order_by(ColesProduct.name)
    )

    return {"woolies": woolies_specials.all(), "coles": coles_specials.all()}


@ui.refreshable
async def current_specials():
    async with async_session() as session:
        specials = await get_specials(session)

        with ui.column().classes("items-center") as column:
            if specials:
                with ui.tabs().props("dense") as tabs:
                    one = ui.tab("🍏 Woolies").classes("text-[#178841]")
                    two = ui.tab("🍎 Coles").classes("text-[#e01a22]")
                with ui.tab_panels(tabs, value=one):
                    with ui.tab_panel(one):
                        await make_specials_grid(specials, "woolies")
                    with ui.tab_panel(two):
                        await make_specials_grid(specials, "coles")

    return column


async def make_specials_grid(specials: dict, supermarket: str):
    with (
        ui.card()
        .style("font-size: 13px;")
        .tight()
        .classes("p-2 w-[90vw] max-w-[600px]")
    ):
        if specials[supermarket]:
            with (
                ui.grid(columns="auto 50px 40px")
                .classes("items-center gap-0 w-full")
                .style("row-gap: 0.4rem")
            ):
                ui.label("Product").classes("border-b")
                ui.label("Price").classes("border-b")
                ui.label("Save").classes("border-b")

                for p in specials[supermarket]:
                    ui.label(
                        re.sub(r"(?i) \d{1,}(?:ml|g|l|kg)", "", p.product.name)
                    ).classes("pr-4").on("click", lambda p=p: product_image_dialog(p))
                    ui.label(f"${p.price / 100:.2f}").on(
                        "click", lambda p=p: price_chart_dialog(p)
                    )
                    ui.label(f"{p.saving}%")
        else:
            ui.label("No specials this week!")


def product_image_dialog(product):
    with ui.dialog() as dialog:
        ui.image(product.image)

    dialog.open()


def price_chart_dialog(product):
    history = [int(x) / 100 for x in product.price_history.split(",")]

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
                "series": [{"type": "line", "data": history}],
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
    async with async_session() as session:
        products = await session.scalars(select(Product))

        for product in products:
            product.update_prices()

        await session.commit()

    current_specials.refresh()


def start_scheduler():
    tr = CronTrigger(day_of_week="wed", hour="3", minute="0")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_specials, trigger=tr)
    scheduler.start()


for suffix in ["", "-precomposed", "-120x120-precomposed", "-120x120"]:
    app.add_static_file(
        local_file="logo.png", url_path=f"/apple-touch-icon{suffix}.png"
    )

if not os.path.exists("products.yaml"):
    open("products.yaml", "w+")

app.on_startup(update_specials)
app.on_startup(start_scheduler)
ui.add_css("page.css", shared=True)

admin = Admin(app, async_engine)

class ProductAdmin(ModelView, model=Product):
    page_size = 50
    column_list = [Product.id, Product.name]
    column_searchable_list = [Product.name]

class WooliesProductAdmin(ModelView, model=WooliesProduct):
    page_size = 50
    column_list = [WooliesProduct.id, WooliesProduct.name]
    column_searchable_list = [WooliesProduct.name]

class ColesProductAdmin(ModelView, model=ColesProduct):
    page_size = 50
    column_list = [ColesProduct.id, ColesProduct.name]
    column_searchable_list = [ColesProduct.name]

admin.add_view(ProductAdmin)
admin.add_view(WooliesProductAdmin)
admin.add_view(ColesProductAdmin)

ui.run(port=8888, title="Price Checker", favicon="🍎")
