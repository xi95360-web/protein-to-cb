"""Run the verified ConformationalBiasing tools over MCP stdio."""
from fastmcp import FastMCP
from tools.cb_pipeline import cb_pipeline_mcp

mcp = FastMCP(name="ConformationalBiasing")
mcp.mount(cb_pipeline_mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
