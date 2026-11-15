from fastapi import FastAPI

app = FastAPI(
    title="ShopSense API",
    description="E-commerce backend with ML-powered features",
    version="0.1.0",
)


@app.get("/")
def root():
    return {"message": "Welcome to the ShopSense API"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/hello/{name}")
def hello(name: str, excited: bool = False):
    greeting = f"Hello, {name}"
    return {"greeting": greeting + "!" if excited else greeting}