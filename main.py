import os
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/node")
async def get_node():
    return {
        "node": os.getenv("HOSTNAME", "unknown"),
        "message": "This request was handled by a Swarm task"
    }
