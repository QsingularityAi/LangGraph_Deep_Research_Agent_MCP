"""
Deep Research Agent - Main Agent Implementation
Combines the best features from the original and improved versions
"""

import os
import re
import json
import asyncio
import warnings
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Suppress warnings
warnings.filterwarnings("ignore", message="Key 'additionalProperties' is not supported in schema")
warnings.filterwarnings("ignore", message="Key '\\$schema' is not supported in schema")

# Configure logging
logging.getLogger("mcp").setLevel(logging.ERROR)
logging.getLogger("langchain_google_genai").setLevel(logging.ERROR)

# MCP and LangChain imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class ResearchQuestion:
    """Structure for research sub-questions"""
    question: str
    priority: int  # 1 (highest) to 5 (lowest)
    answered: bool = False
    answer: str = ""
    sources: List[str] = None
    follow_up_needed: bool = False
    research_method: str = "unknown"  # "web" or "knowledge"
    
    def __post_init__(self):
        if self.sources is None:
            self.sources = []

@dataclass
class ResearchPlan:
    """Structure for the complete research plan"""
    main_question: str
    sub_questions: List[ResearchQuestion]
    research_depth: str  # 'basic', 'intermediate', 'comprehensive'
    estimated_time: int  # in minutes
    current_step: int = 0
    completed: bool = False
    follow_up_questions: List[str] = None
    web_research_count: int = 0
    knowledge_research_count: int = 0
    
    def __post_init__(self):
        if self.follow_up_questions is None:
            self.follow_up_questions = []

class QuietClientSession(ClientSession):
    """Custom notification handler to suppress progress notifications"""
    async def _handle_notification(self, notification):
        if hasattr(notification, 'method') and notification.method != 'notifications/progress':
            await super()._handle_notification(notification)

class DeepResearchAgent:
    """Enhanced Deep Research Agent with proper web search and citation handling"""
    
    def __init__(self):
        self.model = ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"), 
            temperature=0.1,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        self.server_params = StdioServerParameters(
            command="npx",
            env={
                "API_TOKEN": os.getenv("BRIGHTDATA_API_TOKEN", ""),
                "BROWSER_AUTH": os.getenv("BROWSER_AUTH", ""),
                "WEB_UNLOCKER_ZONE": os.getenv("WEB_UNLOCKER_ZONE", "map_web_unlocker"),
                "NODE_OPTIONS": "--max-old-space-size=4096",
            },
            args=["@brightdata/mcp"],
            timeout=30.0,
        )
        
        self.research_history = []
        self.web_search_working = None
        
    def _analyze_question_complexity(self, question: str) -> str:
        """Analyze the complexity of the research question"""
        complex_indicators = [
            "analyze", "compare", "evaluate", "assess", "investigate", "comprehensive",
            "detailed", "in-depth", "thorough", "complete", "full", "extensive"
        ]
        
        basic_indicators = [
            "what is", "who is", "when", "where", "define", "explain", "describe"
        ]
        
        question_lower = question.lower()
        
        complex_count = sum(1 for indicator in complex_indicators if indicator in question_lower)
        basic_count = sum(1 for indicator in basic_indicators if indicator in question_lower)
        
        if complex_count >= 2 or len(question.split()) > 15:
            return "comprehensive"
        elif complex_count >= 1 or len(question.split()) > 8:
            return "intermediate"
        else:
            return "basic"
    
    async def _generate_research_plan(self, main_question: str) -> ResearchPlan:
        """Generate a comprehensive research plan with sub-questions"""
        
        complexity = self._analyze_question_complexity(main_question)
        
        planning_prompt = f"""Create a strategic research plan for: {main_question}

Research Depth: {complexity}

Generate 3-5 specific sub-questions that:
1. Break down the main question logically
2. Cover different aspects of the topic
3. Build upon each other
4. Are specific and focused
5. Can be researched with web tools

Return ONLY a valid JSON object:
{{
    "sub_questions": [
        {{"question": "Specific question 1", "priority": 1}},
        {{"question": "Specific question 2", "priority": 2}},
        {{"question": "Specific question 3", "priority": 3}},
        {{"question": "Specific question 4", "priority": 4}},
        {{"question": "Specific question 5", "priority": 5}}
    ],
    "estimated_time": 15
}}"""

        try:
            messages = [
                {"role": "system", "content": planning_prompt},
                {"role": "user", "content": f"Create research plan for: {main_question}"}
            ]
            
            response = await self.model.ainvoke(messages)
            content = response.content.strip()
            
            # Clean JSON response
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
            
            plan_data = json.loads(content)
            
            sub_questions = [
                ResearchQuestion(
                    question=sq["question"],
                    priority=sq["priority"]
                ) for sq in plan_data["sub_questions"]
            ]
            
            return ResearchPlan(
                main_question=main_question,
                sub_questions=sub_questions,
                research_depth=complexity,
                estimated_time=plan_data.get("estimated_time", 15)
            )
            
        except Exception as e:
            print(f"Error generating research plan: {e}")
            return self._create_fallback_plan(main_question, complexity)
    
    def _create_fallback_plan(self, main_question: str, complexity: str) -> ResearchPlan:
        """Create a fallback research plan"""
        
        questions = [
            ResearchQuestion(f"What are the key facts about {main_question.lower()}?", 1),
            ResearchQuestion(f"What are recent developments in {main_question.lower()}?", 2),
            ResearchQuestion(f"What are the main factors involved in {main_question.lower()}?", 3),
            ResearchQuestion(f"What are expert opinions on {main_question.lower()}?", 4),
            ResearchQuestion(f"What are future trends for {main_question.lower()}?", 5)
        ]
        
        return ResearchPlan(
            main_question=main_question,
            sub_questions=questions,
            research_depth=complexity,
            estimated_time=15
        )
    
    async def _research_sub_question(self, sub_question: ResearchQuestion) -> ResearchQuestion:
        """Research a single sub-question with web tools first, fallback to knowledge"""
        
        print(f"🔍 Researching: {sub_question.question}")
        
        # Try web research first
        web_result = await self._attempt_web_research(sub_question)
        if web_result and self._is_valid_web_research(web_result):
            print(f"✅ Web research successful")
            web_result.research_method = "web"
            return web_result
        
        # Fallback to knowledge-based research
        print(f"📚 Using knowledge-based research")
        knowledge_result = await self._knowledge_based_research(sub_question)
        knowledge_result.research_method = "knowledge"
        return knowledge_result
    
    async def _attempt_web_research(self, sub_question: ResearchQuestion) -> Optional[ResearchQuestion]:
        """Attempt web research using MCP tools"""
        
        research_prompt = f"""You are a web researcher. You MUST use web tools for current information.

MANDATORY STEPS:
1. Use search_engine to find recent information about: {sub_question.question}
2. Use scrape_as_markdown on 2-3 top URLs from search results
3. Provide detailed answer with specific data from scraped content
4. Include proper source citations

Question: {sub_question.question}

REQUIRED FORMAT:
**Sources:**
- [Title] - [URL] (Accessed: {datetime.now().strftime('%Y-%m-%d')})
- [Title] - [URL] (Accessed: {datetime.now().strftime('%Y-%m-%d')})

If web tools fail, respond with: "WEB_RESEARCH_FAILED"
Begin with search_engine tool now."""

        try:
            async with stdio_client(self.server_params) as (read, write):
                async with QuietClientSession(read, write) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                    
                    research_tools = [tool for tool in tools if tool.name in [
                        'search_engine', 'scrape_as_markdown', 'scrape_as_html', 'extract'
                    ]]
                    
                    if not research_tools:
                        return None
                    
                    agent = create_react_agent(self.model, research_tools)
                    
                    messages = [
                        {"role": "system", "content": research_prompt},
                        {"role": "user", "content": f"Research: {sub_question.question}"}
                    ]
                    
                    response = await asyncio.wait_for(
                        agent.ainvoke({"messages": messages}),
                        timeout=90.0
                    )
                    
                    answer = response["messages"][-1].content
                    
                    if "WEB_RESEARCH_FAILED" in answer:
                        return None
                    
                    # Extract sources and validate
                    sources = self._extract_sources(answer)
                    web_sources = [s for s in sources if 'http' in s.lower()]
                    
                    if len(web_sources) < 1:
                        return None
                    
                    # Add web research metadata
                    enhanced_answer = self._add_web_research_metadata(answer, len(web_sources))
                    
                    sub_question.answer = enhanced_answer
                    sub_question.sources = sources
                    sub_question.answered = True
                    
                    return sub_question
                    
        except Exception as e:
            print(f"Web research error: {str(e)}")
            return None
    
    def _is_valid_web_research(self, result: ResearchQuestion) -> bool:
        """Validate that web research actually occurred"""
        if not result or not result.sources:
            return False
        
        web_sources = [s for s in result.sources if 'http' in s.lower()]
        web_indicators = ['according to', 'recent report', 'published', 'announced']
        has_web_language = any(indicator in result.answer.lower() for indicator in web_indicators)
        
        return len(web_sources) >= 1 and has_web_language
    
    async def _knowledge_based_research(self, sub_question: ResearchQuestion) -> ResearchQuestion:
        """Knowledge-based research with clear limitations"""
        
        prompt = f"""Answer this question using your training data knowledge:

Question: {sub_question.question}

Provide:
1. Comprehensive answer with details
2. Key facts and context
3. Relevant examples
4. Current understanding as of training cutoff

End with:
**Sources:**
- Knowledge Base (Training data through 2024)
- Academic Literature
- Industry Documentation"""

        try:
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": sub_question.question}
            ]
            
            response = await self.model.ainvoke(messages)
            answer = response.content
            
            # Ensure sources section
            if "**Sources:**" not in answer:
                answer += "\n\n**Sources:**\n- Knowledge Base (Training data through 2024)\n- Academic Literature\n- Industry Documentation"
            
            # Add limitation notice
            limitation_notice = f"\n\n---\n**📚 Knowledge-Based Research Notice**\n"
            limitation_notice += f"- Information based on training data (may not include latest developments)\n"
            limitation_notice += f"- For current information, configure web research tools\n"
            
            sub_question.answer = answer + limitation_notice
            sub_question.sources = [
                "- Knowledge Base (Training data through 2024)",
                "- Academic Literature",
                "- Industry Documentation"
            ]
            sub_question.answered = True
            
            return sub_question
            
        except Exception as e:
            sub_question.answer = f"Research error: {str(e)}"
            sub_question.sources = ["- Error: Research unavailable"]
            sub_question.answered = True
            return sub_question
    
    def _extract_sources(self, answer: str) -> List[str]:
        """Extract sources from answer text"""
        sources = []
        
        # Look for Sources section
        sources_pattern = r'\*\*Sources:\*\*\s*\n(.*?)(?:\n\n|\*\*|$)'
        sources_match = re.search(sources_pattern, answer, re.DOTALL)
        
        if sources_match:
            sources_text = sources_match.group(1)
            source_lines = [line.strip() for line in sources_text.split('\n') 
                          if line.strip() and line.strip().startswith('-')]
            sources.extend(source_lines)
        
        # Extract URLs
        url_pattern = r'https?://[^\s\)\]\}]+'
        urls = re.findall(url_pattern, answer)
        
        for url in urls:
            if not any(url in source for source in sources):
                sources.append(f"- {url}")
        
        return sources if sources else ["- Research findings"]
    
    def _add_web_research_metadata(self, answer: str, source_count: int) -> str:
        """Add metadata indicating web research was performed"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        metadata = f"\n\n---\n**🌐 Real-time Web Research**\n"
        metadata += f"- Research Date: {timestamp}\n"
        metadata += f"- Web Sources: {source_count}\n"
        metadata += f"- Method: Live web search + content scraping\n"
        
        if "**Sources:**" in answer:
            sources_index = answer.find("**Sources:**")
            return answer[:sources_index] + metadata + "\n\n" + answer[sources_index:]
        else:
            return answer + metadata
    
    async def _generate_follow_up_questions(self, research_plan: ResearchPlan) -> List[str]:
        """Generate intelligent follow-up questions"""
        
        research_summary = f"Main Question: {research_plan.main_question}\n\n"
        for i, sq in enumerate(research_plan.sub_questions, 1):
            if sq.answered:
                research_summary += f"{i}. {sq.question}\nAnswer: {sq.answer[:200]}...\n\n"
        
        prompt = f"""Based on this research, generate 5 follow-up questions that explore:
1. Deeper aspects of the findings
2. Related areas not covered
3. Implications and consequences
4. Future developments
5. Practical applications

Research Summary:
{research_summary}

Return JSON: ["Question 1", "Question 2", "Question 3", "Question 4", "Question 5"]"""

        try:
            response = await self.model.ainvoke([
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate follow-up questions"}
            ])
            
            return json.loads(response.content)[:5]
            
        except Exception as e:
            return [
                f"What are the implications of {research_plan.main_question.lower()}?",
                f"How might this evolve in the future?",
                f"What are the potential challenges?"
            ]
    
    def _compile_final_report(self, research_plan: ResearchPlan) -> str:
        """Compile comprehensive final report"""
        
        # Count research methods
        web_count = sum(1 for sq in research_plan.sub_questions 
                       if sq.answered and sq.research_method == "web")
        knowledge_count = sum(1 for sq in research_plan.sub_questions 
                            if sq.answered and sq.research_method == "knowledge")
        
        research_plan.web_research_count = web_count
        research_plan.knowledge_research_count = knowledge_count
        
        # Collect all sources
        all_sources = set()
        for sq in research_plan.sub_questions:
            if sq.answered and sq.sources:
                all_sources.update(sq.sources)
        
        report = f"""# 🔍 Deep Research Report: {research_plan.main_question}

**📊 Research Overview:**
- **Depth:** {research_plan.research_depth.title()}
- **Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Questions Investigated:** {len([sq for sq in research_plan.sub_questions if sq.answered])}
- **Total Sources:** {len(all_sources)}
- **Web Research:** {web_count} questions
- **Knowledge-based:** {knowledge_count} questions

---

## 📋 Executive Summary

This research investigated "{research_plan.main_question}" through {len(research_plan.sub_questions)} strategic sub-questions using {'real-time web research and ' if web_count > 0 else ''}knowledge-based analysis.

---

## 📄 Detailed Findings

"""
        
        # Add each sub-question and answer
        for i, sq in enumerate(research_plan.sub_questions, 1):
            if sq.answered:
                method_icon = "🌐" if sq.research_method == "web" else "📚"
                report += f"""### {method_icon} {i}. {sq.question}

{sq.answer}

**Sources for this section:**
{chr(10).join(sq.sources) if sq.sources else "- No sources available"}

---

"""
        
        # Add methodology section
        report += f"""## 🔬 Research Methodology

**Research Approach:**
- **Real-time Web Research:** {web_count} questions ({web_count/len(research_plan.sub_questions)*100:.0f}%)
- **Knowledge-based Research:** {knowledge_count} questions ({knowledge_count/len(research_plan.sub_questions)*100:.0f}%)

**Data Sources:**
- Web sources: {len([s for s in all_sources if 'http' in s.lower()])}
- Knowledge base sources: {len([s for s in all_sources if 'knowledge' in s.lower()])}

"""
        
        if web_count == 0:
            report += "**⚠️ Note:** No real-time web research was performed. Configure BRIGHTDATA_API_TOKEN for current information.\n\n"
        
        # Add source bibliography
        if all_sources:
            report += f"""## 📚 Complete Source Bibliography

{chr(10).join(sorted(all_sources))}

"""
        
        # Add follow-up questions
        if research_plan.follow_up_questions:
            report += """## 🔍 Suggested Follow-up Research

"""
            for i, follow_up in enumerate(research_plan.follow_up_questions, 1):
                report += f"{i}. {follow_up}\n"
        
        # Add metadata
        report += f"""

---

## 📊 Research Metadata

- **Quality Score:** {self._calculate_quality_score(research_plan):.1f}/10
- **Research Time:** ~{research_plan.estimated_time} minutes
- **Web Sources:** {len([s for s in all_sources if 'http' in s.lower()])}
- **Methodology:** {'Hybrid (Web + Knowledge)' if web_count > 0 and knowledge_count > 0 else 'Web-based' if web_count > 0 else 'Knowledge-based'}

*Report generated by Deep Research Agent v3.0*"""
        
        return report
    
    def _calculate_quality_score(self, research_plan: ResearchPlan) -> float:
        """Calculate research quality score"""
        score = 0.0
        max_score = 0.0
        
        for sq in research_plan.sub_questions:
            if sq.answered:
                question_score = 2.0  # Base score
                
                # Bonus for web research
                if sq.research_method == "web":
                    question_score += 2.0
                
                # Bonus for multiple sources
                if len(sq.sources) > 1:
                    question_score += 1.0
                
                # Bonus for detailed answers
                if len(sq.answer.split()) > 100:
                    question_score += 1.0
                
                score += question_score
                max_score += 6.0
        
        return (score / max_score) * 10 if max_score > 0 else 0.0
    
    async def ainvoke(self, state, config=None):
        """Main entry point for the research agent"""
        user_input = state.get("input", "")
        
        try:
            # Generate research plan
            print("🔍 Generating research plan...")
            research_plan = await self._generate_research_plan(user_input)
            
            # Execute research
            print(f"📚 Researching {len(research_plan.sub_questions)} sub-questions...")
            for i, sub_question in enumerate(research_plan.sub_questions, 1):
                print(f"   Question {i}/{len(research_plan.sub_questions)}: {sub_question.question}")
                researched_question = await self._research_sub_question(sub_question)
                research_plan.sub_questions[i-1] = researched_question
                await asyncio.sleep(1)
            
            # Generate follow-ups
            print("💡 Generating follow-up questions...")
            research_plan.follow_up_questions = await self._generate_follow_up_questions(research_plan)
            research_plan.completed = True
            
            # Compile final report
            final_report = self._compile_final_report(research_plan)
            
            # Add interactive follow-up section
            if research_plan.follow_up_questions:
                final_report += "\n\n---\n\n**🤔 Would you like to explore any of these follow-up questions?**\n\n"
                for i, question in enumerate(research_plan.follow_up_questions, 1):
                    final_report += f"{i}. {question}\n"
                final_report += "\n*Type the number or ask a new question.*"
            
            return {
                "agent_outcome": type('obj', (object,), {
                    "return_values": {"output": final_report}
                })(),
                "intermediate_steps": []
            }
            
        except Exception as e:
            error_message = f"""# Research Error

Error: {str(e)}

**Troubleshooting:**
1. Check API keys in .env file
2. Verify internet connection
3. Run: python tests/test_environment.py

Try a simpler question or check your configuration."""
            
            return {
                "agent_outcome": type('obj', (object,), {
                    "return_values": {"output": error_message}
                })(),
                "intermediate_steps": []
            }
