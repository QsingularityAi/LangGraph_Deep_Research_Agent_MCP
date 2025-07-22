#!/bin/bash
# Wrapper script for Bright Data MCP

# Export the API token
export API_TOKEN=<YOUR_BRIGHTDATA_API_TOKEN>

# Run the Bright Data MCP server
exec npx @brightdata/mcp
