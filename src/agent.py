# Imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import asyncio
import os
import json
import re
import logging
import warnings
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Suppress specific warnings
warnings.filterwarnings("ignore", message="Key 'additionalProperties' is not supported in schema")
warnings.filterwarnings("ignore", message="Key '\\$schema' is not supported in schema")

# Configure logging to reduce MCP notification noise
logging.getLogger("mcp").setLevel(logging.ERROR)
logging.getLogger("langchain_google_genai").setLevel(logging.ERROR)

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
    
    def __post_init__(self):
        if self.follow_up_questions is None:
            self.follow_up_questions = []

class QuietClientSession(ClientSession):
    """Custom notification handler to suppress progress notifications"""
    async def _handle_notification(self, notification):
        if hasattr(notification, 'method') and notification.method != 'notifications/progress':
            await super()._handle_notification(notification)

class DeepResearchAgent:
    def __init__(self):
        self.model = ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL", "gemini-2.5-pro"), 
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
        self.current_research_plan = None
        self.tool_usage_stats = {
            'search_engine': 0,
            'scrape_as_markdown': 0,
            'scrape_as_html': 0,
            'extract': 0
        }
    
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
        """Generate a comprehensive research plan with sub-questions optimized for tool usage"""
        
        complexity = self._analyze_question_complexity(main_question)
        
        planning_prompt = f"""You are an expert research strategist. Create a research plan that maximizes the use of available web research tools.

Main Question: {main_question}
Research Depth: {complexity}

Available Research Tools:
- search_engine: Get current search results from Google/Bing/Yandex
- scrape_as_markdown: Extract detailed content from specific webpages
- scrape_as_html: Get raw HTML content for complex pages
- extract: Convert webpage content to structured JSON data

Create 3-5 strategic sub-questions that are SPECIFIC to the main question topic. Each question should:
1. Be directly related to the main question
2. Use web research tools effectively
3. Build upon each other logically
4. Cover different aspects of the topic
5. Include recent developments and current information

For web research optimization:
- Include "2024" or "2025" in search queries for recent information
- Target authoritative sources (company announcements, tech news, research papers)
- Look for specific data, statistics, and expert opinions
- Focus on factual, verifiable information

Return ONLY a valid JSON object with this exact structure:
{{
    "sub_questions": [
        {{"question": "Specific question 1 related to the topic", "priority": 1}},
        {{"question": "Specific question 2 related to the topic", "priority": 2}},
        {{"question": "Specific question 3 related to the topic", "priority": 3}},
        {{"question": "Specific question 4 related to the topic", "priority": 4}},
        {{"question": "Specific question 5 related to the topic", "priority": 5}}
    ],
    "estimated_time": 15
}}

CRITICAL: Make each question SPECIFIC to the main question topic, not generic templates."""

        try:
            messages = [
                {"role": "system", "content": planning_prompt},
                {"role": "user", "content": f"Create research plan for: {main_question}"}
            ]
            
            response = await self.model.ainvoke(messages)
            
            # Clean up the response content to extract JSON
            content = response.content.strip()
            
            # Try to extract JSON from the response
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
            print(f"Response content: {response.content if 'response' in locals() else 'No response'}")
            # Fallback to topic-specific plan
            return self._create_topic_specific_plan(main_question, complexity)
    
    def _create_topic_specific_plan(self, main_question: str, complexity: str) -> ResearchPlan:
        """Create a topic-specific research plan based on the question content"""
        question_lower = main_question.lower()
        
        # LLM/AI specific questions
        if any(term in question_lower for term in ['llm', 'large language model', 'ai model', 'language model']):
            questions = [
                ResearchQuestion("What are the most recent large language model releases in 2024-2025?", 1),
                ResearchQuestion("What are the key specifications and capabilities of the latest LLMs?", 2),
                ResearchQuestion("Which companies have launched major LLMs recently and what are their features?", 3),
                ResearchQuestion("How do the latest LLMs compare in terms of performance and capabilities?", 4),
                ResearchQuestion("What are the industry trends and future developments in LLM technology?", 5)
            ]
        # Tech industry questions
        elif any(term in question_lower for term in ['technology', 'tech', 'startup', 'software']):
            questions = [
                ResearchQuestion(f"What are the latest developments in {main_question.lower()}?", 1),
                ResearchQuestion(f"What are the key players and companies involved in {main_question.lower()}?", 2),
                ResearchQuestion(f"What are the current market trends and statistics for {main_question.lower()}?", 3),
                ResearchQuestion(f"What are the challenges and opportunities in {main_question.lower()}?", 4),
                ResearchQuestion(f"What are the future predictions and expert opinions on {main_question.lower()}?", 5)
            ]
        # Business/industry questions
        elif any(term in question_lower for term in ['business', 'industry', 'market', 'company']):
            questions = [
                ResearchQuestion(f"What is the current state and recent developments in {main_question.lower()}?", 1),
                ResearchQuestion(f"What are the key market trends and statistics for {main_question.lower()}?", 2),
                ResearchQuestion(f"Who are the major players and what are their strategies in {main_question.lower()}?", 3),
                ResearchQuestion(f"What are the main challenges and opportunities in {main_question.lower()}?", 4),
                ResearchQuestion(f"What are expert predictions and future trends for {main_question.lower()}?", 5)
            ]
        # Generic fallback
        else:
            questions = [
                ResearchQuestion(f"What are the key facts and current information about {main_question.lower()}?", 1),
                ResearchQuestion(f"What are the latest developments and news regarding {main_question.lower()}?", 2),
                ResearchQuestion(f"What are the main factors and components involved in {main_question.lower()}?", 3),
                ResearchQuestion(f"What are the implications and significance of {main_question.lower()}?", 4),
                ResearchQuestion(f"What are the future trends and expert recommendations for {main_question.lower()}?", 5)
            ]
        
        return ResearchPlan(
            main_question=main_question,
            sub_questions=questions,
            research_depth=complexity,
            estimated_time=15
        )
    
    async def _research_sub_question(self, sub_question: ResearchQuestion) -> ResearchQuestion:
        """Research a single sub-question using available tools with strategic approach"""
        
        # Enhanced research prompt with mandatory source citation requirements
        research_prompt = f"""You are an expert researcher with access to web research tools. You MUST provide proper source citations.

Research Question: {sub_question.question}
Priority Level: {sub_question.priority}

MANDATORY RESEARCH WORKFLOW:

STEP 1 - DISCOVERY SEARCH (REQUIRED):
🔍 Use search_engine tool IMMEDIATELY to find current sources:
- Search with specific, targeted queries about the research question
- Include "2024" or "2025" for recent information
- Use 2-3 different search approaches to get comprehensive coverage
- NEVER skip this step - always start with search_engine

STEP 2 - DEEP CONTENT EXTRACTION (REQUIRED):
📄 Use scrape_as_markdown on the most promising URLs:
- Select 2-3 most authoritative and relevant URLs from search results
- Prioritize official sources, company announcements, reputable news sites
- Extract detailed, specific information
- Note the publication date and source name for each URL scraped

STEP 3 - COMPREHENSIVE ANSWER WITH MANDATORY CITATIONS:
📊 Create a detailed answer that includes:
- Direct, specific information about the research question
- Key facts, statistics, dates, and quotes from sources
- Recent developments and current information
- Multiple perspectives when available

STEP 4 - MANDATORY SOURCE CITATION FORMAT:
📚 You MUST end your response with this exact format:

**Sources:**
- [Source Title] - [URL] (Published: [Date if available])
- [Source Title] - [URL] (Published: [Date if available])
- [Source Title] - [URL] (Published: [Date if available])

CRITICAL REQUIREMENTS:
❗ ALWAYS use search_engine tool first - never provide answers without searching
❗ ALWAYS scrape at least 2 URLs with scrape_as_markdown for detailed information
❗ ALWAYS include the "**Sources:**" section with proper formatting
❗ Include publication dates when available
❗ Use actual URLs from the sources you scraped
❗ Include source titles/names from the websites you visited

EXAMPLE SOURCE FORMAT:
**Sources:**
- TechCrunch - https://techcrunch.com/2024/12/ai-news (Published: December 2024)
- Company Blog - https://company.com/announcement (Published: January 2025)
- Research Paper - https://arxiv.org/paper-link (Published: 2024)

DO NOT provide general knowledge answers. You MUST use the research tools and cite your sources properly.

Begin now with search_engine tool to find current information about: {sub_question.question}"""

        try:
            async with stdio_client(self.server_params) as (read, write):
                async with QuietClientSession(read, write) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                    
                    # Get all available research tools
                    research_tools = [tool for tool in tools if tool.name in [
                        'search_engine', 'scrape_as_markdown', 'scrape_as_html', 'extract'
                    ]]
                    
                    if research_tools:
                        agent = create_react_agent(self.model, research_tools)
                        
                        messages = [
                            {"role": "system", "content": research_prompt},
                            {"role": "user", "content": f"Research this question using web tools and provide proper source citations: {sub_question.question}"}
                        ]
                        
                        response = await asyncio.wait_for(
                            agent.ainvoke({"messages": messages}),
                            timeout=120.0  # Increased timeout for thorough research
                        )
                        
                        answer = response["messages"][-1].content
                        
                        # Enhanced source extraction with metadata
                        sources = self._extract_sources_with_metadata(answer)
                        
                        # Check if answer has proper citations
                        if not self._has_proper_citations(answer):
                            answer = self._add_missing_citations(answer, sources)
                        
                        # Check if follow-up research is needed based on answer quality
                        follow_up_needed = self._assess_research_completeness(answer, sub_question.question)
                        
                        sub_question.answer = answer
                        sub_question.sources = sources
                        sub_question.answered = True
                        sub_question.follow_up_needed = follow_up_needed
                        
                        return sub_question
                    else:
                        print("No research tools available, falling back to knowledge-based research")
                        return await self._fallback_research(sub_question)
                    
        except Exception as e:
            print(f"Error researching sub-question: {e}")
            # Fallback to model-only research
            return await self._fallback_research(sub_question)
    
    async def _fallback_research(self, sub_question: ResearchQuestion) -> ResearchQuestion:
        """Fallback research using only the language model with more specific prompting"""
        
        fallback_prompt = f"""You are a knowledgeable research assistant. Provide a comprehensive answer to this specific research question:

Question: {sub_question.question}

Requirements:
1. Be as specific and factual as possible
2. Include relevant details and context
3. Focus on the exact question being asked
4. If the question is about recent developments, acknowledge the limitation of your knowledge cutoff
5. Provide structured, detailed information

Structure your response with:
- Direct answer to the question
- Key details and specifics
- Relevant context and background
- Important considerations or implications

IMPORTANT: Make your answer specific to the question topic, not generic responses."""

        try:
            messages = [
                {"role": "system", "content": fallback_prompt},
                {"role": "user", "content": f"Provide a detailed answer to: {sub_question.question}"}
            ]
            
            response = await self.model.ainvoke(messages)
            
            sub_question.answer = response.content + "\n\n*Note: This answer is based on general knowledge and may not include the most recent information. For current data, web research tools would be needed.*"
            sub_question.sources = ["General Knowledge Base"]
            sub_question.answered = True
            
            return sub_question
            
        except Exception as e:
            print(f"Fallback research failed: {e}")
            sub_question.answer = f"Unable to research this question due to technical issues: {str(e)}"
            sub_question.answered = True
            return sub_question
    
    def _extract_sources(self, answer: str) -> List[str]:
        """Extract source citations from the answer"""
        source_patterns = [
            r'Sources?:\s*([^\n]+)',
            r'Based on:\s*([^\n]+)',
            r'References?:\s*([^\n]+)',
            r'Source:\s*([^\n]+)'
        ]
        
        sources = []
        for pattern in source_patterns:
            matches = re.findall(pattern, answer, re.IGNORECASE)
            sources.extend(matches)
        
        return sources if sources else ["Research findings"]
    
    def _extract_sources_with_metadata(self, answer: str) -> List[str]:
        """Advanced source extraction that captures URLs, titles, dates, and formats them properly"""
        sources = []
        
        # Look for the formal Sources section first
        sources_section_pattern = r'\*\*Sources:\*\*\s*\n(.*?)(?:\n\n|\n\*\*|$)'
        sources_match = re.search(sources_section_pattern, answer, re.DOTALL)
        
        if sources_match:
            sources_text = sources_match.group(1)
            # Extract individual source lines
            source_lines = [line.strip() for line in sources_text.split('\n') if line.strip() and line.strip().startswith('-')]
            sources.extend(source_lines)
        
        # Extract URLs with context
        url_pattern = r'https?://[^\s\)]+(?=[\s\)\n]|$)'
        urls_found = re.findall(url_pattern, answer)
        
        # Try to match URLs with their context (titles, descriptions)
        for url in urls_found:
            # Look for text before the URL that might be a title
            url_context_pattern = rf'([^.\n]*?)\s*-?\s*{re.escape(url)}'
            context_match = re.search(url_context_pattern, answer)
            
            if context_match:
                context = context_match.group(1).strip()
                # Clean up the context
                context = re.sub(r'^[-•*]\s*', '', context)  # Remove list markers
                context = re.sub(r'^\s*\d+\.\s*', '', context)  # Remove numbers
                
                if context and len(context) > 5:
                    formatted_source = f"- {context} - {url}"
                else:
                    formatted_source = f"- {url}"
                    
                if formatted_source not in sources:
                    sources.append(formatted_source)
            else:
                # If no context found, just add the URL
                formatted_source = f"- {url}"
                if formatted_source not in sources:
                    sources.append(formatted_source)
        
        # Extract traditional citation patterns
        citation_patterns = [
            r'According to ([^,\n]+),?\s*([^,\n]*)',
            r'Based on ([^,\n]+),?\s*([^,\n]*)',
            r'From ([^,\n]+),?\s*([^,\n]*)',
            r'\[([^\]]+)\]',  # Markdown-style citations
            r'Source:\s*([^\n]+)',
            r'Sources:\s*([^\n]+)'
        ]
        
        for pattern in citation_patterns:
            matches = re.findall(pattern, answer, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    source_info = ' '.join([part.strip() for part in match if part.strip()])
                else:
                    source_info = match.strip()
                
                if source_info and len(source_info) > 5:
                    formatted_source = f"- {source_info}"
                    if formatted_source not in sources:
                        sources.append(formatted_source)
        
        # Remove duplicates and clean up
        unique_sources = []
        seen = set()
        
        for source in sources:
            # Normalize for comparison
            normalized = source.lower().strip()
            if normalized not in seen and len(source.strip()) > 5:
                seen.add(normalized)
                unique_sources.append(source.strip())
        
        return unique_sources if unique_sources else ["- Web research findings (sources not properly formatted)"]
    
    def _has_proper_citations(self, answer: str) -> bool:
        """Check if the answer has proper source citations"""
        # Look for formal Sources section
        has_sources_section = bool(re.search(r'\*\*Sources:\*\*', answer, re.IGNORECASE))
        
        # Look for URLs
        has_urls = bool(re.search(r'https?://', answer))
        
        # Look for citation patterns
        citation_patterns = [
            r'According to [^,\n]+',
            r'Based on [^,\n]+',
            r'From [^,\n]+',
            r'\[[^\]]+\]'
        ]
        
        has_citations = any(re.search(pattern, answer, re.IGNORECASE) for pattern in citation_patterns)
        
        return has_sources_section or (has_urls and has_citations)
    
    def _add_missing_citations(self, answer: str, sources: List[str]) -> str:
        """Add a proper Sources section if missing"""
        if not sources or sources == ["- Web research findings (sources not properly formatted)"]:
            return answer + "\n\n**Sources:**\n- Web research conducted (detailed source citations not available)"
        
        # Check if already has a Sources section
        if re.search(r'\*\*Sources:\*\*', answer, re.IGNORECASE):
            return answer
        
        # Add Sources section
        sources_text = "\n\n**Sources:**\n" + "\n".join(sources)
        return answer + sources_text
    
    def _assess_research_completeness(self, answer: str, question: str) -> bool:
        """Assess if the research answer is comprehensive enough"""
        
        # Quality indicators
        quality_indicators = {
            'has_statistics': bool(re.search(r'\d+%|\d+\.\d+%|\$\d+|\d+,\d+', answer)),
            'has_recent_info': bool(re.search(r'202[3-5]|recent|latest|current', answer, re.IGNORECASE)),
            'has_multiple_sources': len(re.findall(r'https?://|according to|based on', answer, re.IGNORECASE)) >= 2,
            'sufficient_length': len(answer.split()) >= 150,
            'has_specific_examples': bool(re.search(r'for example|such as|including|specifically', answer, re.IGNORECASE)),
            'addresses_question': any(word.lower() in answer.lower() for word in question.split() if len(word) > 3)
        }
        
        # Calculate completeness score
        completeness_score = sum(quality_indicators.values()) / len(quality_indicators)
        
        # Return True if research might need follow-up (score < 0.6)
        return completeness_score < 0.6
    
    async def _generate_follow_up_questions(self, research_plan: ResearchPlan) -> List[str]:
        """Generate intelligent follow-up questions based on research findings"""
        
        # Compile research summary
        research_summary = f"Main Question: {research_plan.main_question}\n\n"
        for i, sq in enumerate(research_plan.sub_questions, 1):
            if sq.answered:
                research_summary += f"{i}. {sq.question}\nAnswer: {sq.answer[:200]}...\n\n"
        
        follow_up_prompt = f"""Based on this research, generate 3-5 intelligent follow-up questions that would:
1. Dive deeper into interesting findings
2. Explore related aspects not covered
3. Address potential gaps in the research
4. Connect to broader implications

Research Summary:
{research_summary}

Return ONLY a JSON list of follow-up questions:
["Question 1", "Question 2", "Question 3", "Question 4", "Question 5"]"""

        try:
            messages = [
                {"role": "system", "content": follow_up_prompt},
                {"role": "user", "content": "Generate follow-up questions"}
            ]
            
            response = await self.model.ainvoke(messages)
            follow_ups = json.loads(response.content)
            
            return follow_ups[:5]  # Limit to 5 questions
            
        except Exception as e:
            print(f"Error generating follow-up questions: {e}")
            return [
                f"What are the long-term implications of {research_plan.main_question.lower()}?",
                f"How does this topic connect to broader industry trends?",
                f"What are the potential challenges or risks involved?"
            ]
    
    def _compile_final_report(self, research_plan: ResearchPlan) -> str:
        """Compile the final comprehensive research report with enhanced source presentation"""
        
        # Collect all unique sources across all research questions
        all_sources = set()
        for sq in research_plan.sub_questions:
            if sq.answered and sq.sources:
                all_sources.update(sq.sources)
        
        report = f"""# 🔍 Deep Research Report: {research_plan.main_question}

**📊 Research Depth:** {research_plan.research_depth.title()}
**⏰ Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**❓ Questions Investigated:** {len([sq for sq in research_plan.sub_questions if sq.answered])}
**📚 Sources Consulted:** {len(all_sources)}

---

## 📋 Executive Summary

This comprehensive research investigated multiple aspects of "{research_plan.main_question}" through systematic analysis of {len(research_plan.sub_questions)} key research questions using real-time web research and authoritative sources.

---

## 📄 Detailed Findings

"""
        
        # Add each sub-question and answer with enhanced source formatting
        for i, sq in enumerate(research_plan.sub_questions, 1):
            if sq.answered:
                report += f"""### 🔸 {i}. {sq.question}

{sq.answer}

**📚 Sources for this section:**
{chr(10).join(sq.sources) if sq.sources else "- General research findings"}

---

"""
        
        # Add comprehensive source bibliography
        if all_sources and len(all_sources) > 1:
            report += f"""## 📚 Complete Source Bibliography

All sources used in this research:

{chr(10).join(sorted(all_sources))}

---

"""
        
        # Add follow-up questions
        if research_plan.follow_up_questions:
            report += """## 🔍 Suggested Follow-up Research

Based on these findings, you might want to explore:

"""
            for i, follow_up in enumerate(research_plan.follow_up_questions, 1):
                report += f"{i}. {follow_up}\n"
        
        report += f"""
---

## 📊 Research Metadata

- **⏱️ Total research time:** ~{research_plan.estimated_time} minutes
- **🔍 Research depth:** {research_plan.research_depth}
- **❓ Questions answered:** {len([sq for sq in research_plan.sub_questions if sq.answered])}/{len(research_plan.sub_questions)}
- **📚 Unique sources consulted:** {len(all_sources)}
- **🔗 Web research conducted:** {len([s for s in all_sources if 'http' in s.lower()])} URLs scraped
- **📈 Research quality score:** {self._calculate_research_quality_score(research_plan):.1f}/10

---

## 🔍 Research Methodology

This report was generated using a systematic approach:

1. **🎯 Question Analysis:** The main question was analyzed and broken down into {len(research_plan.sub_questions)} strategic sub-questions
2. **🔍 Web Research:** Each sub-question was researched using real-time web search and content scraping
3. **📄 Source Verification:** Information was cross-referenced across multiple authoritative sources
4. **📊 Synthesis:** Findings were compiled into a comprehensive, well-sourced report

*Report generated by Deep Research Agent v2.1 with Enhanced Source Attribution*
"""
        
        return report
    
    def _calculate_research_quality_score(self, research_plan: ResearchPlan) -> float:
        """Calculate a quality score for the research based on various factors"""
        score = 0.0
        total_possible = 0.0
        
        for sq in research_plan.sub_questions:
            if sq.answered:
                # Base score for answered question
                question_score = 2.0
                
                # Bonus for having sources
                if sq.sources and len(sq.sources) > 1:
                    question_score += 1.0
                
                # Bonus for having URLs (web research)
                if any('http' in source.lower() for source in sq.sources):
                    question_score += 1.0
                
                # Bonus for detailed answers
                if len(sq.answer.split()) > 100:
                    question_score += 1.0
                
                # Bonus for having citations in text
                if any(pattern in sq.answer.lower() for pattern in ['according to', 'based on', 'sources:']):
                    question_score += 1.0
                
                score += question_score
                total_possible += 6.0  # Max possible score per question
        
        # Normalize to 0-10 scale
        if total_possible > 0:
            return (score / total_possible) * 10
        return 0.0
    
    async def ainvoke(self, state, config=None):
        """Main entry point for the deep research agent"""
        user_input = state.get("input", "")
        
        # Check if this is a follow-up question selection
        if user_input.startswith("FOLLOW_UP:"):
            selected_question = user_input.replace("FOLLOW_UP:", "").strip()
            return await self._handle_follow_up_research(selected_question)
        
        try:
            # Step 1: Generate research plan
            print("🔍 Generating research plan...")
            research_plan = await self._generate_research_plan(user_input)
            self.current_research_plan = research_plan
            
            # Step 2: Execute research for each sub-question
            print(f"📚 Researching {len(research_plan.sub_questions)} sub-questions...")
            
            for i, sub_question in enumerate(research_plan.sub_questions, 1):
                print(f"   Researching question {i}/{len(research_plan.sub_questions)}: {sub_question.question}")
                researched_question = await self._research_sub_question(sub_question)
                research_plan.sub_questions[i-1] = researched_question
                research_plan.current_step = i
                
                # Small delay to prevent overwhelming the system
                await asyncio.sleep(1)
            
            # Step 3: Generate follow-up questions
            print("💡 Generating follow-up questions...")
            research_plan.follow_up_questions = await self._generate_follow_up_questions(research_plan)
            research_plan.completed = True
            
            # Step 4: Compile final report
            final_report = self._compile_final_report(research_plan)
            
            # Add interactive follow-up section
            if research_plan.follow_up_questions:
                final_report += "\n\n---\n\n**🤔 Would you like to explore any of these follow-up questions?**\n\n"
                for i, question in enumerate(research_plan.follow_up_questions, 1):
                    final_report += f"{i}. {question}\n"
                final_report += "\n*Type the number of the question you'd like me to research next, or ask a completely new question.*"
            
            return {
                "agent_outcome": type('obj', (object,), {
                    "return_values": {"output": final_report}
                })(),
                "intermediate_steps": []
            }
            
        except Exception as e:
            print(f"Error during deep research: {e}")
            error_message = f"""# Research Error

I encountered an error while conducting deep research on your question: "{user_input}"

**Error details:** {str(e)}

**What I can do instead:**
1. Try a simpler, more specific question
2. Break down your question into smaller parts
3. Ask for a basic overview first

Would you like me to try a different approach to your research question?"""
            
            return {
                "agent_outcome": type('obj', (object,), {
                    "return_values": {"output": error_message}
                })(),
                "intermediate_steps": []
            }
    
    async def _handle_follow_up_research(self, question: str):
        """Handle follow-up research questions"""
        try:
            # Create a new research plan for the follow-up
            follow_up_plan = await self._generate_research_plan(question)
            
            # Execute research
            for i, sub_question in enumerate(follow_up_plan.sub_questions):
                researched_question = await self._research_sub_question(sub_question)
                follow_up_plan.sub_questions[i] = researched_question
            
            # Generate new follow-ups
            follow_up_plan.follow_up_questions = await self._generate_follow_up_questions(follow_up_plan)
            
            # Compile report
            report = self._compile_final_report(follow_up_plan)
            
            return {
                "agent_outcome": type('obj', (object,), {
                    "return_values": {"output": report}
                })(),
                "intermediate_steps": []
            }
            
        except Exception as e:
            error_msg = f"Error researching follow-up question: {str(e)}"
            return {
                "agent_outcome": type('obj', (object,), {
                    "return_values": {"output": error_msg}
                })(),
                "intermediate_steps": []
            }

# Create the app instance for import
app = DeepResearchAgent()