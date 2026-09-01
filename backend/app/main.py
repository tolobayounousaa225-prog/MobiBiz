from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .migrations import run_startup_migrations
from .routers import (
    admin,
    auth,
    categories,
    customers,
    dashboard,
    employees,
    finances,
    notifications,
    orders,
    products,
    public,
    reports,
    shops,
    stock,
    subscription,
)

run_startup_migrations()

app = FastAPI(title="MobiBiz API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(shops.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(customers.router)
app.include_router(orders.router)
app.include_router(stock.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(employees.router)
app.include_router(finances.router)
app.include_router(notifications.router)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(subscription.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
