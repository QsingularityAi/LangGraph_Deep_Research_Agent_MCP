"""
Utility functions for Deep Research Agent
"""

import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

def extract_sources_from_text(text: str) -> List[str]:
    """Extract sources from research text with improved parsing"""
    sources = []
    
    # Look for formal Sources section
    sources_pattern = r'\*\*Sources:\*\*\s*\n(.*?)(?:\n\n|\*\*|$)'
    sources_match = re.search(sources_pattern, text, re.DOTALL)
    
    if sources_match:
        sources_text = sources_match.group(1)
        source_lines = [line.strip() for line in sources_text.split('\n') 
                      if line.strip() and (line.strip().startswith('-') or line.strip().startswith('•'))]
        sources.extend(source_lines)
    
    # Extract URLs with context
    url_pattern = r'https?://[^\s\)\]\}]+'
    urls = re.findall(url_pattern, text)
    
    for url in urls:
        # Try to find context around the URL
        url_context_pattern = rf'([^.\n]*?)\s*[-–—]?\s*{re.escape(url)}'
        context_match = re.search(url_context_pattern, text)
        
        if context_match:
            context = context_match.group(1).strip()
            context = re.sub(r'^[-•*]\s*', '', context)  # Remove list markers
            
            if context and len(context) > 5:
                source_line = f"- {context} - {url}"
            else:
                source_line = f"- {url}"
        else:
            source_line = f"- {url}"
        
        # Avoid duplicates
        if not any(url in existing for existing in sources):
            sources.append(source_line)
    
    # Clean and format sources
    formatted_sources = []
    for source in sources:
        if not source.strip():
            continue
            
        formatted_source = source.strip()
        if not formatted_source.startswith('-'):
            formatted_source = f"- {formatted_source}"
            
        formatted_sources.append(formatted_source)
    
    return formatted_sources if formatted_sources else ["- Research findings"]

def format_research_output(output: str) -> str:
    """Format research output with enhanced visual hierarchy"""
    
    # Clean up the output
    formatted = output.strip()
    
    # Enhance markdown formatting with icons
    formatted = re.sub(r'^# (.+)$', r'# 🔍 \1', formatted, flags=re.MULTILINE)
    formatted = re.sub(r'^## (.+)$', r'## 📋 \1', formatted, flags=re.MULTILINE)
    formatted = re.sub(r'^### (.+)$', r'### 🔸 \1', formatted, flags=re.MULTILINE)
    
    # Enhance specific sections
    replacements = [
        ('**Research Depth:**', '**📊 Research Depth:**'),
        ('**Completed:**', '**⏰ Completed:**'),
        ('**Questions Investigated:**', '**❓ Questions Investigated:**'),
        ('**Sources:**', '**📚 Sources:**'),
        ('**Total research time:**', '**⏱️ Total research time:**'),
        ('**Research Quality Score:**', '**🎯 Research Quality Score:**'),
        ('**Real-time Web Research**', '**🌐 Real-time Web Research**'),
        ('**Knowledge-Based Research Notice**', '**📚 Knowledge-Based Research Notice**')
    ]
    
    for old, new in replacements:
        formatted = formatted.replace(old, new)
    
    # Improve URL formatting
    url_pattern = r'(https?://[^\s\)]+)'
    formatted = re.sub(url_pattern, r'[\1](\1)', formatted)
    
    # Enhance source lists
    formatted = re.sub(r'^- (.+)$', r'🔗 \1', formatted, flags=re.MULTILINE)
    
    return formatted

def extract_follow_up_questions(output: str) -> List[tuple]:
    """Extract follow-up questions from research output"""
    
    patterns = [
        r'(\d+)\.\s+([^\n]+)',  # Numbered list
        r'[-•]\s*([^\n]+)',     # Bulleted list
    ]
    
    # Find follow-up section
    follow_up_patterns = [
        r'Would you like to explore any of these follow-up questions\?\*\*\n\n(.*?)(?:\n\n|\*Type|$)',
        r'follow-up questions:\*\*\n\n(.*?)(?:\n\n|\*Type|$)',
        r'Suggested Follow-up Research\n\n(.*?)(?:\n\n|---|\*\*|$)'
    ]
    
    questions = []
    
    for pattern in follow_up_patterns:
        follow_up_match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
        if follow_up_match:
            questions_text = follow_up_match.group(1)
            
            for q_pattern in patterns:
                matches = re.findall(q_pattern, questions_text)
                if matches:
                    if isinstance(matches[0], tuple):
                        questions.extend([(int(num), question.strip()) for num, question in matches])
                    else:
                        questions.extend([(i+1, q.strip()) for i, q in enumerate(matches)])
                    break
            
            if questions:
                break
    
    return questions

def analyze_research_quality(output: str) -> Optional[str]:
    """Analyze and report research quality indicators"""
    
    # Extract quality score
    quality_score_match = re.search(r'Research quality score:\s*([0-9.]+)/10', output, re.IGNORECASE)
    
    # Count sources
    sources_section = re.search(r'\*\*Sources:\*\*\s*\n(.*?)(?:\n\n|\*\*|$)', output, re.DOTALL)
    source_count = 0
    web_source_count = 0
    
    if sources_section:
        sources_text = sources_section.group(1)
        sources = [line.strip() for line in sources_text.split('\n') if line.strip().startswith('-')]
        source_count = len(sources)
        web_source_count = len([s for s in sources if 'http' in s.lower()])
    
    # Check for web research indicators
    web_research_indicators = [
        "Real-time Web Research",
        "Research Date:",
        "Web Sources:",
        "Live web search"
    ]
    
    has_web_research = any(indicator in output for indicator in web_research_indicators)
    
    # Create quality summary
    if quality_score_match or source_count > 0 or has_web_research:
        quality_summary = "**📊 Research Quality Summary:**\n"
        
        if quality_score_match:
            score = quality_score_match.group(1)
            quality_summary += f"🎯 **Quality Score:** {score}/10\n"
        
        if source_count > 0:
            quality_summary += f"📚 **Total Sources:** {source_count}\n"
            if web_source_count > 0:
                quality_summary += f"🌐 **Web Sources:** {web_source_count}\n"
        
        if has_web_research:
            quality_summary += f"✅ **Research Type:** Real-time web research\n"
        else:
            quality_summary += f"📖 **Research Type:** Knowledge-based analysis\n"
        
        return quality_summary
    
    return None

def validate_json_response(response: str) -> Dict[str, Any]:
    """Validate and parse JSON response with error handling"""
    
    try:
        # Clean response
        content = response.strip()
        
        if content.startswith('```json'):
            content = content.replace('```json', '').replace('```', '').strip()
        elif content.startswith('```'):
            content = content.replace('```', '').strip()
        
        return json.loads(content)
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response: {str(e)}")

def create_timestamp() -> str:
    """Create formatted timestamp"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file operations"""
    
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    
    return sanitized

def calculate_research_score(web_count: int, knowledge_count: int, total_sources: int) -> float:
    """Calculate research quality score"""
    
    base_score = 5.0  # Base score
    
    # Web research bonus
    if web_count > 0:
        base_score += min(web_count * 1.5, 3.0)
    
    # Source count bonus
    if total_sources > 0:
        base_score += min(total_sources * 0.5, 2.0)
    
    # Balance penalty for too much knowledge-based research
    if knowledge_count > web_count and web_count == 0:
        base_score -= 1.0
    
    return min(max(base_score, 0.0), 10.0)

def clean_text(text: str) -> str:
    """Clean and normalize text"""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters that might cause issues
    text = re.sub(r'[^\w\s\-\.\,\!\?\:\;\(\)\[\]\{\}\"\'\/\@\#\$\%\^\&\*\+\=\<\>\~\`]', '', text)
    
    return text.strip()

def extract_key_terms(text: str, max_terms: int = 10) -> List[str]:
    """Extract key terms from text"""
    
    # Simple keyword extraction based on frequency and length
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    
    # Filter common words
    common_words = {'that', 'this', 'with', 'from', 'they', 'have', 'were', 'been', 
                   'their', 'said', 'each', 'which', 'them', 'will', 'many', 'some'}
    
    filtered_words = [word for word in words if word not in common_words]
    
    # Count frequency
    word_freq = {}
    for word in filtered_words:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    # Sort by frequency and return top terms
    sorted_terms = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    
    return [term[0] for term in sorted_terms[:max_terms]]
