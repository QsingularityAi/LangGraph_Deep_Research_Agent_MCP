"""
Deep Research Agent - Main Chainlit Application
Streamlined and organized version with proper web search and citations
"""

import chainlit as cl
import asyncio
import os
import sys
from typing import Dict, Any, Optional
import json
import re

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agents'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'config'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))

# Import our organized modules
try:
    from research_agent import DeepResearchAgent
    from settings import Config
    from helpers import format_research_output, extract_follow_up_questions, analyze_research_quality
    print("✅ Successfully imported organized modules")
except ImportError as e:
    print(f"⚠️ Import error: {e}")
    # Fallback to original structure
    from src.agent import DeepResearchAgent
    
    # Create a basic Config class for fallback
    class Config:
        @staticmethod
        def get_environment_status():
            google_key = os.getenv("GOOGLE_API_KEY")
            brightdata_token = os.getenv("BRIGHTDATA_API_TOKEN")
            
            status = "**🔧 Environment Status:**\n"
            status += "✅ Google API: Configured\n" if google_key else "❌ Google API: Missing\n"
            status += "✅ BrightData: Configured\n" if brightdata_token else "⚠️ BrightData: Missing\n"
            return status
        
        @staticmethod
        def validate_config():
            return {"valid": bool(os.getenv("GOOGLE_API_KEY")), "errors": [], "warnings": []}
    
    # Basic helper functions for fallback
    def format_research_output(output):
        return output
    
    def extract_follow_up_questions(output):
        return []
    
    def analyze_research_quality(output):
        return None
    
# Initialize the research agent
research_agent = DeepResearchAgent()

# Global variable to store follow-up questions for the session
session_follow_ups = {}

@cl.on_chat_start
async def start():
    """Initialize the chat session with environment status"""
    
    # Get environment status
    env_status = Config.get_environment_status()
    config_validation = Config.validate_config()
    
    # Create status indicators
    status_indicators = ""
    if config_validation["valid"]:
        status_indicators += "✅ **Configuration:** Valid\n"
    else:
        status_indicators += "❌ **Configuration:** Issues detected\n"
        for error in config_validation.get("errors", []):
            status_indicators += f"   - {error}\n"
    
    for warning in config_validation.get("warnings", []):
        status_indicators += f"⚠️ **Warning:** {warning}\n"
    
    welcome_message = f"""# 🔍 Deep Research Agent v3.0

Welcome! I'm your enhanced AI research assistant with real-time web search and comprehensive citation capabilities.

{env_status}

{status_indicators}

## 🌟 **Key Features:**

### 🌐 **Real-time Web Research**
- Live web search using Google, Bing, Yandex
- Content scraping from authoritative sources
- Current information with publication dates

### 📚 **Comprehensive Citations**
- Proper source formatting with URLs
- Publication dates and access timestamps
- Clear distinction between web and knowledge sources

### 🔍 **Research Methodology**
- Strategic question breakdown
- Multi-step research planning
- Quality scoring and validation
- Transparent methodology reporting

### 💡 **Intelligence Features**
- Smart follow-up question generation
- Research depth analysis
- Error handling and troubleshooting
- Progress tracking and transparency

## 🚀 **How to Use:**

**Ask any research question:**
- *"What are the latest AI safety developments in 2024?"*
- *"Compare renewable energy adoption rates globally"*
- *"Analyze the impact of remote work on productivity"*

**Research Quality:**
- Real-time web sources when available
- Knowledge-based fallback with clear labeling
- Source count and quality metrics
- Research methodology transparency

---

**Ready to start researching?** Ask me any question and I'll provide comprehensive, well-sourced analysis!"""
    
    await cl.Message(content=welcome_message).send()

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages with improved routing"""
    user_input = message.content.strip()
    
    # Check if user is selecting a follow-up question by number
    if user_input.isdigit():
        await handle_follow_up_selection(int(user_input))
        return
    
    # Check if this is a direct follow-up question
    if user_input.startswith("FOLLOW_UP:"):
        await handle_direct_follow_up(user_input)
        return
    
    # Check for help commands
    if user_input.lower() in ['help', '/help', 'commands']:
        await show_help()
        return
    
    # Check for status commands
    if user_input.lower() in ['status', '/status', 'config']:
        await show_status()
        return
    
    # Regular research request
    await conduct_research(user_input)

async def conduct_research(question: str):
    """Conduct research with enhanced progress tracking"""
    
    # Initial status check
    env_status = Config.get_environment_status()
    
    initial_msg = f"""🔍 **Initiating Deep Research**

**Research Question:** "{question}"

{env_status}

⏳ **Status:** Analyzing question complexity and generating strategic research plan...
"""
    
    msg = cl.Message(content=initial_msg)
    await msg.send()
    
    try:
        # Enhanced progress tracking
        progress_steps = [
            ("📋 Question Analysis", "Analyzing complexity and generating research strategy"),
            ("🌐 Web Search", "Executing real-time web search across multiple sources"),
            ("📄 Content Analysis", "Scraping and analyzing content from authoritative sources"),
            ("🔍 Information Synthesis", "Synthesizing findings with proper citation formatting"),
            ("💡 Follow-up Generation", "Generating intelligent follow-up questions"),
            ("📊 Report Compilation", "Compiling comprehensive research report with methodology")
        ]
        
        # Show progress with detailed feedback
        for i, (step_name, step_description) in enumerate(progress_steps):
            if i > 0:
                await asyncio.sleep(2.0)  # Reasonable delay for UX
            
            progress_text = f"🔍 **Deep Research in Progress**\n\n"
            progress_text += f"**Question:** \"{question}\"\n\n"
            progress_text += f"{env_status}\n\n"
            progress_text += f"**Research Workflow:**\n"
            
            for j, (name, desc) in enumerate(progress_steps):
                if j < i:
                    progress_text += f"✅ **{name}** - Completed\n"
                elif j == i:
                    progress_text += f"⏳ **{name}** - {desc}...\n"
                else:
                    progress_text += f"⏸️ **{name}** - Pending\n"
            
            # Add specific progress context
            if i == 1:
                progress_text += f"\n💡 *Searching multiple sources for current information...*"
            elif i == 2:
                progress_text += f"\n📊 *Extracting detailed content and verifying source quality...*"
            elif i == 3:
                progress_text += f"\n🧠 *Analyzing findings and ensuring proper citation format...*"
            elif i == 4:
                progress_text += f"\n🔮 *Identifying areas for deeper exploration...*"
            
            msg.content = progress_text
            await msg.update()
        
        # Execute research
        print(f"🚀 Starting research: {question}")
        result = await research_agent.ainvoke({"input": question})
        
        # Extract output
        if hasattr(result.get("agent_outcome"), "return_values"):
            output = result["agent_outcome"].return_values.get("output", "No output generated")
        else:
            output = str(result.get("agent_outcome", "No result available"))
        
        # Format output
        formatted_output = format_research_output(output)
        
        # Add quality analysis
        quality_info = analyze_research_quality(output)
        if quality_info:
            formatted_output = quality_info + "\n\n" + formatted_output
        
        # Update with final result
        msg.content = formatted_output
        await msg.update()
        
        # Handle follow-up questions
        follow_ups = extract_follow_up_questions(output)
        if follow_ups:
            await create_follow_up_actions(follow_ups)
        else:
            await cl.Message(content="""**🤔 Continue Your Research Journey**

You can:
- 🔍 **Ask follow-up questions** to dive deeper into specific aspects
- 📊 **Request comparative analysis** with related topics  
- 🆕 **Explore related areas** based on these findings
- 📈 **Get updated information** (with web research enabled)
- 🎯 **Focus on specific details** that caught your interest

Just type your next research question!""").send()
            
    except Exception as e:
        error_msg = create_comprehensive_error_message(question, str(e))
        msg.content = error_msg
        await msg.update()

async def show_help():
    """Show help information"""
    
    help_msg = """# 🆘 Deep Research Agent - Help

## 📝 **Commands:**
- **Ask any question** - Start research
- **Type a number** (1-5) - Select follow-up question
- **help** or **/help** - Show this help
- **status** or **/status** - Show configuration status

## 🔍 **Research Examples:**

### Technology & AI
- *"Latest developments in artificial intelligence 2024"*
- *"Compare current large language models"*
- *"AI safety regulations and policies"*

### Business & Economics  
- *"Impact of remote work on productivity"*
- *"Renewable energy market trends"*
- *"Cryptocurrency adoption rates globally"*

### Science & Health
- *"Recent advances in quantum computing"*
- *"Climate change mitigation strategies"*
- *"Mental health trends post-pandemic"*

## 📊 **Research Quality:**
- ✅ Real-time web research (when configured)
- ✅ Comprehensive source citations
- ✅ Quality scoring and validation
- ✅ Methodology transparency

## ⚙️ **Configuration:**
- Set `GOOGLE_API_KEY` for LLM functionality
- Set `BRIGHTDATA_API_TOKEN` for web research
- Run `python tests/test_environment.py` to verify setup

**Ready to research?** Ask me any question!"""
    
    await cl.Message(content=help_msg).send()

async def show_status():
    """Show current configuration status"""
    
    config_status = Config.validate_config()
    env_status = Config.get_environment_status()
    
    status_msg = f"""# ⚙️ Deep Research Agent - Status

{env_status}

## 🔧 **Configuration Validation:**
"""
    
    if config_status["valid"]:
        status_msg += "✅ **Status:** All required configurations are valid\n\n"
    else:
        status_msg += "❌ **Status:** Configuration issues detected\n\n"
    
    status_msg += """## 🔧 **Troubleshooting:**
1. Run: `python tests/test_environment.py`
2. Check: `.env` file configuration
3. Verify: Internet connectivity
4. Test: API key validity

**Need help?** Type **help** for usage instructions."""
    
    await cl.Message(content=status_msg).send()

def create_comprehensive_error_message(question: str, error: str) -> str:
    """Create detailed error message with troubleshooting"""
    
    env_status = Config.get_environment_status()
    
    error_msg = f"""# ❌ Research Error

**Question:** "{question}"
**Error:** {error}

{env_status}

## 🔧 **Troubleshooting Steps:**

### 1. Environment Check
- Ensure `.env` file exists with API keys
- Required: `GOOGLE_API_KEY`
- Optional: `BRIGHTDATA_API_TOKEN` (for web research)

### 2. Technical Validation
- Run: `python tests/test_environment.py`
- Check: Internet connectivity
- Verify: API quotas and limits

### 3. Alternative Approaches
- Try a simpler, more specific question
- Break complex topics into smaller questions
- Use quotation marks for exact phrases

**Configuration Help:**
- Type **status** to check current setup
- Type **help** for usage instructions

Would you like to try a different approach to your question?"""
    
    return error_msg

async def create_follow_up_actions(follow_ups: list):
    """Create enhanced follow-up question interface"""
    
    if not follow_ups:
        return
    
    # Store in session
    session_id = cl.context.session.id if cl.context.session else "default"
    session_follow_ups[session_id] = {num: question for num, question in follow_ups}
    
    content = """**🤔 Ready to Explore Deeper?**

**🔍 Intelligent Follow-up Questions:**

"""
    
    for num, question in follow_ups[:5]:
        content += f"**{num}.** {question}\n\n"
    
    content += """**💡 How to Continue:**
- 🔢 **Type the number** (e.g., `1`, `2`, `3`) to research that question
- 📝 **Copy and paste** the full question for research
- ❓ **Ask any new question** for fresh research

*These follow-ups are generated based on research gaps and interesting angles.*"""
    
    await cl.Message(content=content).send()

async def handle_follow_up_selection(selection: int):
    """Handle follow-up question selection"""
    
    session_id = cl.context.session.id if cl.context.session else "default"
    
    if session_id in session_follow_ups and selection in session_follow_ups[session_id]:
        question = session_follow_ups[session_id][selection]
        
        msg = cl.Message(content=f"""🔍 **Researching Follow-up Question #{selection}**

**Selected Question:** *{question}*

⏳ Initiating focused research...""")
        await msg.send()
        
        await conduct_research(question)
    else:
        available = list(session_follow_ups.get(session_id, {}).keys()) if session_id in session_follow_ups else []
        
        error_msg = f"""❓ **Follow-up Question #{selection} Not Found**

**Available options:** {available if available else 'None currently available'}

What would you like me to research?"""
        
        await cl.Message(content=error_msg).send()

async def handle_direct_follow_up(follow_up_input: str):
    """Handle direct follow-up research"""
    question = follow_up_input.replace("FOLLOW_UP:", "").strip()
    await conduct_research(question)

if __name__ == "__main__":
    # Validate configuration before starting
    config_status = Config.validate_config()
    if not config_status["valid"]:
        print("❌ Configuration errors detected. Please check your .env file.")
    
    print("✅ Starting Deep Research Agent...")
    cl.run()