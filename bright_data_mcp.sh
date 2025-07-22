#!/bin/bash
# Wrapper script for Bright Data MCP

# Export the API token
export API_TOKEN=16d0b4b9b0d7b9061d726e723f9d63cf22df6112dc66a39d01e2b2008cbacba5

# Run the Bright Data MCP server
exec npx @brightdata/mcp
