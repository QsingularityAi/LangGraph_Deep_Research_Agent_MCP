import chainlit as cl
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import StructuredTool
from typing import Dict, List, Any, Optional
from mcp import ClientSession
import json
import asyncio
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class SimpleMCPTool:
    """Simple wrapper for MCP tools that avoids complex schema issues"""
    
    def __init__(self, mcp_name: str, tool_name: str, tool_description: str, session: ClientSession):
        self.mcp_name = mcp_name
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.session = session
        
    async def _call(self, input_text: str):
        """Execute the MCP tool with simple string input and UI tracking"""
        
        # Create a step to show tool execution in the UI
        async with cl.Step(name=f"🔧 {self.tool_name}", type="tool") as step:
            try:
                # Clean the input text - remove JSON wrapping if present
                cleaned_input = input_text.strip()
                if cleaned_input.startswith('{"') and cleaned_input.endswith('"}'):
                    try:
                        import json
                        parsed = json.loads(cleaned_input)
                        if isinstance(parsed, dict) and len(parsed) == 1:
                            # Extract the single value from the JSON
                            cleaned_input = list(parsed.values())[0]
                    except:
                        pass  # Use original input if JSON parsing fails
                
                # Update step with input details
                step.input = f"Input: {cleaned_input[:100]}{'...' if len(cleaned_input) > 100 else ''}"
                
                print(f"[{self.tool_name}] calling with input: {cleaned_input}")
                
                # Smart parameter detection based on tool name and input format
                params = self._determine_parameters(cleaned_input)
                
                # Try the most likely parameter format first
                result = await self.session.call_tool(self.tool_name, params)
                
                # Process the result more thoroughly for better citations
                if hasattr(result, 'content'):
                    if isinstance(result.content, list):
                        # Handle list of content (common for search results)
                        content_parts = []
                        for item in result.content:
                            if hasattr(item, 'text'):
                                content_parts.append(item.text)
                            elif isinstance(item, dict):
                                # Extract URLs and titles for citations
                                if 'url' in item and 'title' in item:
                                    content_parts.append(f"Title: {item['title']}\nURL: {item['url']}\nContent: {item.get('description', item.get('snippet', str(item)))}")
                                else:
                                    content_parts.append(str(item))
                            else:
                                content_parts.append(str(item))
                        processed_result = "\n---\n".join(content_parts)
                    else:
                        processed_result = str(result.content)
                else:
                    processed_result = str(result)
                
                # Add tool context for better agent understanding
                if self.tool_name == 'search_engine':
                    processed_result = f"SEARCH RESULTS for '{cleaned_input}':\n{processed_result}\n\nNOTE: Use 'scrape_as_markdown' or 'scrape_as_html' to get full content from specific URLs above."
                elif self.tool_name in ['scrape_as_markdown', 'scrape_as_html']:
                    processed_result = f"SCRAPED CONTENT from {cleaned_input}:\n{processed_result}\n\nNOTE: This is the full content from the webpage. Extract key information and quotes for your response."
                
                # Update step with output summary
                output_preview = processed_result[:200] + "..." if len(processed_result) > 200 else processed_result
                step.output = f"✅ Success ({len(processed_result)} chars)\n\nPreview:\n{output_preview}"
                
                print(f"[{self.tool_name}] result length: {len(processed_result)} chars")
                return processed_result
                
            except Exception as e1:
                # Update step to show we're trying fallback
                step.output = f"⚠️ Primary method failed, trying fallback approaches..."
                
                # Fallback with different parameter combinations
                fallback_params = [
                    {"input": cleaned_input},
                    {"text": cleaned_input}, 
                    {"command": cleaned_input},
                    {"content": cleaned_input}
                ]
                
                for params in fallback_params:
                    try:
                        result = await self.session.call_tool(self.tool_name, params)
                        processed_result = json.dumps(result.content) if hasattr(result, 'content') else str(result)
                        
                        # Update step with successful fallback
                        step.output = f"✅ Success with fallback parameters: {list(params.keys())}\n\nResult: {processed_result[:200]}..."
                        
                        print(f"[{self.tool_name}] success with parameters: {list(params.keys())}")
                        return processed_result
                    except Exception:
                        continue
                
                # All attempts failed
                error_msg = f"❌ Error calling tool {self.tool_name}: {str(e1)}"
                step.output = error_msg
                print(error_msg)
                return error_msg
    
    def _determine_parameters(self, input_text: str):
        """Determine the best parameters based on tool name and input format"""
        # Check if input looks like a URL
        is_url = input_text.startswith(('http://', 'https://'))
        
        # Tool-specific parameter mapping
        if self.tool_name in ['scrape_as_markdown', 'scrape_as_html'] and is_url:
            return {"url": input_text}
        elif self.tool_name.startswith('web_data_') and is_url:
            return {"url": input_text}
        elif self.tool_name == 'search_engine':
            return {"query": input_text}
        elif self.tool_name == 'extract':
            return {"content": input_text}
        else:
            # Default fallback
            return {"query": input_text}
    
    def to_langchain_tool(self):
        """Convert to LangChain StructuredTool with simple schema"""
        
        class SimpleInputModel(BaseModel):
            input_text: str = Field(description=f"Input for {self.tool_name}. {self.tool_description}")
        
        return StructuredTool(
            name=f"{self.mcp_name}_{self.tool_name}",
            description=f"[{self.mcp_name}] {self.tool_description}",
            func=lambda input_text: asyncio.create_task(self._call(input_text)),
            args_schema=SimpleInputModel,
            coroutine=self._call
        )


class MCPAgentManager:
    """Manages the LangGraph agent with dynamic MCP tools"""
    
    def __init__(self):
        self.agent = None
        self.tools = []
        self.mcp_tools_map = {}  # Maps tool names to MCP connections
        
    def update_tools(self, new_tools: List[StructuredTool]):
        """Update the agent with new tools"""
        self.tools = new_tools
        
        # Recreate the agent with updated tools and recursion limit
        llm = self._get_llm()
        try:
            # Create agent with configuration to prevent infinite loops
            self.agent = create_react_agent(llm, self.tools)
            print(f"✅ Agent created successfully with {len(self.tools)} tools")
        except Exception as e:
            print(f"❌ Error creating agent with tools: {e}")
            # If agent creation fails, try with no tools as fallback
            try:
                self.agent = create_react_agent(llm, [])
                print("⚠️ Agent created without tools as fallback")
            except Exception as e2:
                print(f"❌ Failed to create agent even without tools: {e2}")
                self.agent = None
        
    def _get_llm(self):
        """Get the configured Google Gemini LLM"""
        # Get model selection from user session or use default
        model_name = cl.user_session.get("gemini_model", "gemini-2.5-flash")
        
        # Ensure Google API key is set
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=google_api_key,
            temperature=1.0,  # Balanced for research accuracy
            convert_system_message_to_human=True,
            max_output_tokens=15000,  # Longer responses for detailed research
            # Parameters optimized for research tasks
            top_p=0.9,
            top_k=30,
        )
    
    async def run(self, message: str, message_history: List[Dict[str, str]] = None):
        """Run the agent with the given message"""
        if not self.agent:
            return "❌ No agent initialized. Please connect at least one MCP server."
        
        # Create a step to show agent reasoning
        async with cl.Step(name="🧠 Agent Reasoning", type="llm") as step:
            # Enhanced strategic instructions with loop prevention
            enhanced_message = f"""You are an advanced research assistant with access to powerful web scraping and data collection tools. 

USER QUESTION: {message}

CRITICAL INSTRUCTIONS:
1. PLAN FIRST: Think about what tools you need BEFORE using them
2. USE TOOLS EFFICIENTLY: Don't repeat the same tool call with the same parameters
3. STOP AFTER SUCCESS: When you get good results from a tool, use that information to answer
4. MAXIMUM 3 TOOL CALLS: You should be able to answer most questions with 1-3 tool calls

STRATEGIC APPROACH:
1. ANALYZE the question to determine what information is needed
2. PLAN which tools to use:
   - Use 'search_engine' first to get recent information and identify key sources
   - Use 'scrape_as_markdown' with specific URLs to get detailed content
   - Use specialized tools (web_data_*) for platform-specific information if relevant

3. EXECUTE efficiently:
   - Start with search_engine to find current information
   - Then scrape 1-2 most relevant sources for detailed information
   - Provide comprehensive answer based on results

4. PROVIDE RESPONSE with:
   - Summary answer first
   - Key findings with evidence
   - Source citations as clickable flags, not full URLs
   - Stop after providing the answer

SOURCE CITATION FORMAT:
- Instead of full URLs, use website names as clickable links
- Format: [Website Name](full_url) 
- Examples: 
  * [Apple](https://www.apple.com/iphone-15-pro/)
  * [Best Buy](https://www.bestbuy.com/site/reviews/apple-iphone-15-pro/)
  * [Amazon](https://www.amazon.com/Apple-iPhone-15-Pro/)
  * [TechCrunch](https://techcrunch.com/article-name/)
  * [GitHub](https://github.com/QwenLM/Qwen3)
- This creates clean, professional source flags instead of messy URLs

RESPONSE FORMAT EXAMPLE:
## iPhone 15 Pro Reviews & Pricing

**Summary**: The iPhone 15 Pro starts at $999 and receives excellent reviews.

**Key Findings**:
- According to [Apple](https://apple.com), the iPhone 15 Pro features titanium design
- [Best Buy](https://bestbuy.com) customer reviews average 4.5/5 stars
- [Amazon](https://amazon.com) shows 4.4/5 rating across 2,000+ reviews

**Sources**: [Apple](https://apple.com) | [Best Buy](https://bestbuy.com) | [Amazon](https://amazon.com)

IMPORTANT: 
- If a tool fails, try a different approach instead of repeating
- Use the information you gather to provide a complete answer
- Don't get stuck in loops - provide an answer based on available information

Begin your research now."""
            
            step.input = f"Research Query: {message}"
            
            # Format message history for the agent
            if message_history:
                messages = message_history + [{"role": "user", "content": enhanced_message}]
            else:
                messages = [{"role": "user", "content": enhanced_message}]
            
            try:
                # Run the agent with recursion limit and timeout
                result = await asyncio.wait_for(
                    self.agent.ainvoke(
                        {"messages": messages},
                        config={"recursion_limit": 10}  # Limit recursion to prevent loops
                    ),
                    timeout=120  # 2-minute timeout for research
                )
                
                # Update step with completion status
                step.output = "✅ Agent reasoning completed successfully"
                return result
                
            except asyncio.TimeoutError:
                step.output = "⏰ Agent reasoning timed out after 2 minutes"
                return "⏰ Research is taking longer than expected. The agent may be conducting comprehensive research. Please try a more specific question if this continues."
            except Exception as e:
                step.output = f"❌ Agent reasoning failed: {str(e)}"
                if "recursion_limit" in str(e).lower():
                    return "🔄 The agent hit the recursion limit while trying to research your question. This usually means it's getting stuck trying the same tools repeatedly. Please try rephrasing your question or asking for something more specific."
                return f"❌ Error running agent: {str(e)}"


# Global agent manager
agent_manager = MCPAgentManager()


@cl.on_mcp_connect
async def on_mcp_connect(connection, session: ClientSession):
    """Called when an MCP connection is established"""
    # Create a step to show connection process
    async with cl.Step(name=f"🔌 Connecting to {connection.name}", type="tool") as step:
        try:
            # List available tools from the MCP server
            result = await session.list_tools()
            
            step.output = f"✅ Connected with {len(result.tools)} tools available"
            
            # Process tool metadata with simplified approach
            tools = []
            tool_wrappers = []
            
            for t in result.tools:
                print(f"Processing tool: {t.name}")
                
                # Create simplified wrapper for each tool
                wrapper = SimpleMCPTool(
                    mcp_name=connection.name,
                    tool_name=t.name,
                    tool_description=t.description,
                    session=session
                )
                
                # Convert to LangChain tool
                try:
                    langchain_tool = wrapper.to_langchain_tool()
                    tools.append(langchain_tool)
                    tool_wrappers.append(wrapper)
                    print(f"✅ Successfully created tool: {t.name}")
                except Exception as e:
                    print(f"⚠️ Failed to create tool {t.name}: {e}")
                    continue
                
                # Store mapping for later use
                agent_manager.mcp_tools_map[f"{connection.name}_{t.name}"] = {
                    "mcp_name": connection.name,
                    "tool_name": t.name,
                    "session": session
                }
            
            # Store tools in user session
            mcp_tools = cl.user_session.get("mcp_tools", {})
            mcp_tools[connection.name] = {
                "tools": tools,
                "wrappers": tool_wrappers,
                "raw_tools": [{
                    "name": t.name,
                    "description": t.description,
                } for t in result.tools]
            }
            cl.user_session.set("mcp_tools", mcp_tools)
            
            # Update the agent with all available tools
            all_tools = []
            for conn_tools in mcp_tools.values():
                all_tools.extend(conn_tools["tools"])
            
            agent_manager.update_tools(all_tools)
            
            # Success message
            await cl.Message(
                content=f"🎯 **Research Agent Ready** - {len(tools)} tools from **{connection.name}** loaded and ready for research!"
            ).send()
            
        except Exception as e:
            step.output = f"❌ Connection failed: {str(e)}"
            await cl.Message(
                content=f"❌ Error connecting to **{connection.name}**: {str(e)}",
                author="System"
            ).send()


@cl.on_mcp_disconnect
async def on_mcp_disconnect(name: str, session: ClientSession):
    """Called when an MCP connection is terminated"""
    await cl.Message(
        content=f"🔌 Disconnected from MCP server: **{name}**"
    ).send()
    
    # Remove tools from this connection
    mcp_tools = cl.user_session.get("mcp_tools", {})
    if name in mcp_tools:
        del mcp_tools[name]
        cl.user_session.set("mcp_tools", mcp_tools)
        
        # Remove from tools map
        keys_to_remove = [k for k in agent_manager.mcp_tools_map.keys() if k.startswith(f"{name}_")]
        for key in keys_to_remove:
            del agent_manager.mcp_tools_map[key]
        
        # Update the agent with remaining tools
        all_tools = []
        for conn_tools in mcp_tools.values():
            all_tools.extend(conn_tools["tools"])
        
        agent_manager.update_tools(all_tools)


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session"""
    # Send welcome message
    await cl.Message(
        content="""# 🔍 Advanced Research Agent Ready!

✅ **MCP Server**: Ready to connect (click 'Add MCP' in sidebar)
🤖 **Model**: Google Gemini 2.5 Flash optimized for research
🎯 **Features**: Multi-source research with tool execution visibility
📊 **UI Enhancement**: See exactly which tools are running in real-time

**Quick Start**: Connect an MCP server and ask me any research question!

*Example*: "What are the latest updates about Qwen LLM?"
"""
    ).send()
    
    # Initialize user session
    cl.user_session.set("mcp_tools", {})
    cl.user_session.set("message_history", [])
    
    # Set default Gemini model
    cl.user_session.set("gemini_model", "gemini-2.5-flash")


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages"""
    # Get message history
    message_history = cl.user_session.get("message_history", [])
    
    # Check if any MCP servers are connected
    mcp_tools = cl.user_session.get("mcp_tools", {})
    if not mcp_tools:
        await cl.Message(
            content="⚠️ No MCP servers connected. Please click **'Add MCP'** in the sidebar to connect to an MCP server first."
        ).send()
        return
    
    # Show thinking message
    thinking_msg = cl.Message(content="🤔 Starting research process...")
    await thinking_msg.send()
    
    try:
        # Run the agent
        result = await agent_manager.run(message.content, message_history)
        
        # Extract the final message from the agent
        if isinstance(result, dict) and "messages" in result:
            # Get the last assistant message
            final_message = None
            for msg in reversed(result["messages"]):
                if hasattr(msg, 'type') and msg.type == "ai":
                    final_message = msg.content
                    break
                elif hasattr(msg, 'content') and hasattr(msg, 'role'):
                    if getattr(msg, 'role', None) == "assistant":
                        final_message = msg.content
                        break
            
            if final_message:
                # Update thinking message with the response
                thinking_msg.content = f"# 🎯 Research Complete\n\n{final_message}"
                await thinking_msg.update()
            else:
                thinking_msg.content = "❌ I couldn't generate a proper response. Please try again."
                await thinking_msg.update()
        else:
            thinking_msg.content = f"# 🎯 Research Complete\n\n{str(result)}"
            await thinking_msg.update()
        
        # Update message history
        message_history.append({"role": "user", "content": message.content})
        if isinstance(result, dict) and "messages" in result:
            for msg in result["messages"]:
                if hasattr(msg, 'type') and msg.type == "ai":
                    message_history.append({"role": "assistant", "content": msg.content})
                elif hasattr(msg, 'content') and hasattr(msg, 'role'):
                    if getattr(msg, 'role', None) == "assistant":
                        message_history.append({"role": "assistant", "content": msg.content})
        
        cl.user_session.set("message_history", message_history)
        
    except Exception as e:
        thinking_msg.content = f"❌ Research failed: {str(e)}\n\nPlease try rephrasing your question or check your MCP connection."
        await thinking_msg.update()


@cl.on_settings_update
async def on_settings_update(settings):
    """Handle settings updates"""
    # Update Gemini model selection
    if "gemini_model" in settings:
        cl.user_session.set("gemini_model", settings["gemini_model"])
        
        # Recreate the agent with the new model
        mcp_tools = cl.user_session.get("mcp_tools", {})
        all_tools = []
        for conn_tools in mcp_tools.values():
            all_tools.extend(conn_tools["tools"])
        
        agent_manager.update_tools(all_tools)
        
        await cl.Message(
            content=f"✅ Gemini model updated to: **{settings['gemini_model']}**"
        ).send()


# Remove the unused @cl.step function since we're now using cl.Step directly
# The old function is not needed anymore

if __name__ == "__main__":
    cl.run()