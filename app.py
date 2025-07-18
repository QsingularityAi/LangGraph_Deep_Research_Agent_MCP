import chainlit as cl
import asyncio
from src.agent import DeepResearchAgent
from typing import Dict, Any, Optional
import json
import re

# Initialize the research agent
research_agent = DeepResearchAgent()

# Global variable to store follow-up questions for the session
session_follow_ups = {}

@cl.on_chat_start
async def start():
    """Initialize the chat session"""
    await cl.Message(
        content="""# 🔍 Deep Research Agent

Welcome! I'm your AI research assistant powered by advanced web search and analysis capabilities.

**What I can do:**
- Conduct comprehensive research on any topic
- Break down complex questions into strategic sub-questions
- Provide detailed, well-sourced answers
- Generate intelligent follow-up questions
- Create structured research reports

**How to use:**
Just ask me any research question! For example:
- "What are the latest developments in AI safety?"
- "Analyze the impact of remote work on productivity"
- "Compare renewable energy technologies"

**Features:**
✅ Multi-step research planning
✅ Web search and content scraping
✅ Source citations
✅ Follow-up question suggestions
✅ Comprehensive final reports

What would you like me to research today?"""
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    user_input = message.content.strip()
    
    # Check if user is selecting a follow-up question by number
    if user_input.isdigit():
        await handle_follow_up_selection(int(user_input))
        return
    
    # Check if this is a direct follow-up question
    if user_input.startswith("FOLLOW_UP:"):
        await handle_direct_follow_up(user_input)
        return
    
    # Regular research request
    await conduct_research(user_input)

async def conduct_research(question: str):
    """Conduct research and display results"""
    
    # Show initial message
    msg = cl.Message(content="🔍 **Starting deep research...**\n\nGenerating research plan...")
    await msg.send()
    
    try:
        # Create progress tracking
        progress_steps = [
            "📋 Generating research plan",
            "🔍 Researching sub-questions", 
            "💡 Generating follow-up questions",
            "📄 Compiling final report"
        ]
        
        # Show progress with separate messages for better compatibility
        for i, step in enumerate(progress_steps):
            if i > 0:
                await asyncio.sleep(1)  # Small delay for better UX
            
            progress_text = "🔍 **Deep Research in Progress**\n\n"
            for j, s in enumerate(progress_steps):
                if j < i:
                    progress_text += f"✅ {s}\n"
                elif j == i:
                    progress_text += f"⏳ {s}...\n"
                else:
                    progress_text += f"⏸️ {s}\n"
            
            # Update the message content directly
            msg.content = progress_text
            await msg.update()
        
        # Execute the research
        result = await research_agent.ainvoke({"input": question})
        
        # Extract the output
        if hasattr(result.get("agent_outcome"), "return_values"):
            output = result["agent_outcome"].return_values.get("output", "No output generated")
        else:
            output = str(result.get("agent_outcome", "No result"))
        
        # Parse and format the output
        formatted_output = format_research_output(output)
        
        # Update with final result
        msg.content = formatted_output
        await msg.update()
        
        # Check if there are follow-up questions and create action buttons
        follow_ups = extract_follow_up_questions(output)
        if follow_ups:
            await create_follow_up_actions(follow_ups)
            
    except Exception as e:
        error_msg = f"""# ❌ Research Error

I encountered an error while researching your question:

**Error:** {str(e)}

**Suggestions:**
- Try rephrasing your question
- Make your question more specific
- Break complex topics into smaller questions

Would you like to try again with a different approach?"""
        
        msg.content = error_msg
        await msg.update()

async def handle_follow_up_selection(selection: int):
    """Handle follow-up question selection by number"""
    
    session_id = cl.context.session.id if cl.context.session else "default"
    
    # Get the stored follow-up questions for this session
    if session_id in session_follow_ups and selection in session_follow_ups[session_id]:
        question = session_follow_ups[session_id][selection]
        
        msg = cl.Message(content=f"🔍 **Researching follow-up question #{selection}:**\n\n*{question}*")
        await msg.send()
        
        # Conduct research on the selected question
        await conduct_research(question)
    else:
        error_msg = f"""❓ I couldn't find follow-up question #{selection}. 

Please try:
- Selecting a number from the available options above
- Copying and pasting the full question
- Asking a new research question

What would you like me to research?"""
        
        await cl.Message(content=error_msg).send()

async def handle_direct_follow_up(follow_up_input: str):
    """Handle direct follow-up research"""
    question = follow_up_input.replace("FOLLOW_UP:", "").strip()
    
    msg = cl.Message(content="🔍 **Researching follow-up question...**")
    await msg.send()
    
    try:
        result = await research_agent._handle_follow_up_research(question)
        
        if hasattr(result.get("agent_outcome"), "return_values"):
            output = result["agent_outcome"].return_values.get("output", "No output generated")
        else:
            output = str(result.get("agent_outcome", "No result"))
        
        formatted_output = format_research_output(output)
        msg.content = formatted_output
        await msg.update()
        
        # Check for new follow-ups
        follow_ups = extract_follow_up_questions(output)
        if follow_ups:
            await create_follow_up_actions(follow_ups)
            
    except Exception as e:
        msg.content = f"Error researching follow-up: {str(e)}"
        await msg.update()

def format_research_output(output: str) -> str:
    """Format the research output for better display with enhanced source highlighting"""
    
    # Clean up the output
    formatted = output.strip()
    
    # Enhance markdown formatting
    formatted = re.sub(r'^# (.+)$', r'# 🔍 \1', formatted, flags=re.MULTILINE)
    formatted = re.sub(r'^## (.+)$', r'## 📋 \1', formatted, flags=re.MULTILINE)
    formatted = re.sub(r'^### (.+)$', r'### 🔸 \1', formatted, flags=re.MULTILINE)
    
    # Add icons to common sections
    formatted = formatted.replace('**Research Depth:**', '**📊 Research Depth:**')
    formatted = formatted.replace('**Completed:**', '**⏰ Completed:**')
    formatted = formatted.replace('**Questions Investigated:**', '**❓ Questions Investigated:**')
    formatted = formatted.replace('**Sources:**', '**📚 Sources:**')
    formatted = formatted.replace('**Total research time:**', '**⏱️ Total research time:**')
    formatted = formatted.replace('**Sources Consulted:**', '**📚 Sources Consulted:**')
    formatted = formatted.replace('**Sources for this section:**', '**📚 Sources for this section:**')
    
    # Highlight URLs to make them clickable
    url_pattern = r'(https?://[^\s\)]+)'
    formatted = re.sub(url_pattern, r'[\1](\1)', formatted)
    
    # Make source lists more prominent
    formatted = re.sub(r'^- (.+)$', r'🔗 \1', formatted, flags=re.MULTILINE)
    
    # Add emphasis to source sections
    formatted = formatted.replace('Complete Source Bibliography', '📚 **Complete Source Bibliography**')
    formatted = formatted.replace('Research Methodology', '🔍 **Research Methodology**')
    
    return formatted

def extract_follow_up_questions(output: str) -> list:
    """Extract follow-up questions from the output"""
    
    # Look for numbered follow-up questions
    pattern = r'(\d+)\.\s+([^\n]+)'
    
    # Find the section with follow-up questions
    follow_up_section = re.search(r'Would you like to explore any of these follow-up questions\?\*\*\n\n(.*?)(?:\n\n|\*Type the number|$)', output, re.DOTALL)
    
    if follow_up_section:
        questions_text = follow_up_section.group(1)
        matches = re.findall(pattern, questions_text)
        return [(int(num), question.strip()) for num, question in matches]
    
    return []

async def create_follow_up_actions(follow_ups: list):
    """Create follow-up questions as numbered options"""
    
    if not follow_ups:
        return
    
    # Store follow-ups in session for reference
    session_id = cl.context.session.id if cl.context.session else "default"
    session_follow_ups[session_id] = {num: question for num, question in follow_ups}
    
    # Create a formatted message with numbered options
    content = "**🤔 Interested in diving deeper?**\n\n"
    content += "**Available follow-up questions:**\n\n"
    
    for num, question in follow_ups[:5]:  # Limit to 5 questions
        content += f"**{num}.** {question}\n\n"
    
    content += "💡 **To research a follow-up question:**\n"
    content += "- Type the number (e.g., `1`, `2`, `3`)\n"
    content += "- Or copy and paste the full question\n"
    content += "- Or ask any new research question!"
    
    await cl.Message(content=content).send()

if __name__ == "__main__":
    cl.run()