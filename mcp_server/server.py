from .app import mcp

try:
    from . import tools
    from . import prompts
    from . import resources

    print("ALL IMPORTS OK")

except Exception as e:
    print("IMPORT ERROR:")
    print(e)
    raise


if __name__ == "__main__":
    mcp.run(
    transport="http",
    host="127.0.0.1",
    port=8000
)