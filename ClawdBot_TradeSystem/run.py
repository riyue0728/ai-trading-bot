import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.trade_bot:app",
        host="0.0.0.0",
        port=80,
        reload=False,
        log_level="info"
    )
