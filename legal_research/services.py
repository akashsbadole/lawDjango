import time
import re
import json
from typing import List, Dict, Tuple, Any
import google.generativeai as genai
from decouple import config
from django.core.files.base import ContentFile
import PyPDF2
from docx import Document as DocxDocument
from io import BytesIO


class GeminiAIService:
    """
    Service class for interacting with Google Gemini AI API.
    """
    
    def __init__(self):
        """Initialize the Gemini AI service."""
        api_key = config('GEMINI_API_KEY', default='')
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH", 
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
    
    def research_legal_query(self, query: str, query_type: str, context: Dict = None) -> Tuple[str, int]:
        """
        Process a legal research query using Gemini AI.
        
        Args:
            query: The legal research question
            query_type: Type of legal research
            context: Additional context (case, client, documents, etc.)
            
        Returns:
            Tuple of (response_text, tokens_used)
        """
        prompt = self._build_legal_prompt(query, query_type, context)
        
        try:
            start_time = time.time()
            response = self.model.generate_content(
                prompt,
                safety_settings=self.safety_settings,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=2048,
                )
            )
            
            processing_time = time.time() - start_time
            
            if response.candidates:
                response_text = response.candidates[0].content.parts[0].text
                tokens_used = self._estimate_tokens(response_text)
                return response_text, tokens_used
            else:
                raise Exception("No response generated")
                
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    def analyze_document(self, document_content: str, analysis_type: str, specific_questions: str = "") -> Tuple[str, int]:
        """
        Analyze a document using Gemini AI.
        
        Args:
            document_content: Text content of the document
            analysis_type: Type of analysis required
            specific_questions: Specific questions about the document
            
        Returns:
            Tuple of (analysis_result, tokens_used)
        """
        prompt = self._build_document_analysis_prompt(document_content, analysis_type, specific_questions)
        
        try:
            response = self.model.generate_content(
                prompt,
                safety_settings=self.safety_settings,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=2048,
                )
            )
            
            if response.candidates:
                analysis_result = response.candidates[0].content.parts[0].text
                tokens_used = self._estimate_tokens(analysis_result)
                return analysis_result, tokens_used
            else:
                raise Exception("No analysis generated")
                
        except Exception as e:
            raise Exception(f"Document analysis error: {str(e)}")
    
    def extract_sources(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Extract legal sources from AI response.
        
        Args:
            response_text: The AI response containing sources
            
        Returns:
            List of source dictionaries
        """
        sources = []
        
        # Look for citation patterns in the response
        citation_patterns = [
            r'(\d+\)\s*([^,\n]+(?:v\.[^,\n]+)?\s*\d+\s*[A-Za-z]+\s*\d+))',
            r'([A-Z][a-z]+\s+v\.\s*[A-Z][a-z]+\s*\d+\s*[A-Za-z]+\s*\d+)',
            r'(\d+\s*[A-Za-z]+\s*\d+\s*\(\d+\)\s*\d+)',
            r'([A-Z][a-z]+\s+Code\s+§\s*\d+)',
        ]
        
        for pattern in citation_patterns:
            matches = re.findall(pattern, response_text)
            for match in matches:
                citation = match if isinstance(match, str) else match[0]
                if citation and len(citation.strip()) > 10:
                    sources.append({
                        'title': citation[:200],
                        'source_type': 'case_law' if 'v.' in citation.lower() else 'statute',
                        'citation': citation,
                        'url': '',
                        'summary': f"Legal source referenced in research: {citation}",
                        'relevance_explanation': "Cited as relevant authority for the legal question",
                        'jurisdiction': '',
                        'decision_date': None,
                        'court': ''
                    })
        
        return sources[:10]  # Limit to 10 sources
    
    def _build_legal_prompt(self, query: str, query_type: str, context: Dict = None) -> str:
        """Build a comprehensive prompt for legal research."""
        
        base_prompt = f"""
You are an expert legal researcher with extensive knowledge of case law, statutes, regulations, and legal principles. 
Your task is to provide a comprehensive legal research response to the following query.

QUERY TYPE: {query_type.upper()}
QUESTION: {query}

CONTEXTUAL INFORMATION:
"""
        
        if context:
            if context.get('jurisdiction'):
                base_prompt += f"Jurisdiction: {context['jurisdiction']}\n"
            
            if context.get('practice_area'):
                base_prompt += f"Practice Area: {context['practice_area']}\n"
            
            if context.get('relevant_facts'):
                base_prompt += f"Relevant Facts: {context['relevant_facts']}\n"
            
            if context.get('specific_requirements'):
                base_prompt += f"Specific Requirements: {context['specific_requirements']}\n"
            
            if context.get('case_context'):
                base_prompt += f"Case Context: {context['case_context']}\n"
            
            if context.get('client_context'):
                base_prompt += f"Client Context: {context['client_context']}\n"
            
            if context.get('documents_context'):
                base_prompt += f"Relevant Documents: {context['documents_context']}\n"
        
        base_prompt += f"""

INSTRUCTIONS:
1. Provide a thorough legal analysis based on current law as of your knowledge cutoff
2. Cite relevant case law, statutes, and regulations
3. Explain the legal principles and how they apply to the facts
4. Identify any potential counterarguments or limitations
5. Provide practical recommendations or next steps
6. Include proper legal citations in Bluebook format
7. Structure your response with clear headings and bullet points where appropriate

RESPONSE FORMAT:
## Legal Analysis
[Your detailed legal analysis here]

## Key Authorities
[List and explain the most relevant cases, statutes, and regulations]

## Application to Facts
[Explain how the law applies to the specific facts provided]

## Potential Issues and Considerations
[Identify any potential legal issues, risks, or considerations]

## Recommendations
[Provide practical recommendations and next steps]

## Sources
[List all cited authorities with proper citations]

Please ensure your response is accurate, well-researched, and legally sound.
"""
        
        return base_prompt
    
    def _build_document_analysis_prompt(self, document_content: str, analysis_type: str, specific_questions: str = "") -> str:
        """Build a prompt for document analysis."""
        
        analysis_prompts = {
            'summary': """
Provide a comprehensive summary of the following legal document. Include:
1. Main purpose and key provisions
2. Important dates, parties, and terms
3. Key obligations and rights
4. Notable clauses or conditions
5. Overall legal implications
""",
            'key_points': """
Extract and present the key points from the following legal document. Organize by:
1. Critical terms and definitions
2. Main obligations and responsibilities
3. Important dates and deadlines
4. Rights and remedies
5. Risk factors or concerns
""",
            'legal_issues': """
Identify potential legal issues in the following document. Analyze:
1. Regulatory compliance concerns
2. Potential liabilities
3. Ambiguous or unclear provisions
4. Conflicts with applicable laws
5. Areas requiring legal clarification
""",
            'risk_assessment': """
Conduct a risk assessment of the following legal document. Evaluate:
1. High-risk clauses and provisions
2. Potential legal liabilities
3. Compliance risks
4. Financial exposure
5. Recommended risk mitigation strategies
""",
            'contract_analysis': """
Analyze the following contract document. Examine:
1. Contract formation and validity
2. Essential terms and conditions
3. Performance obligations
4. Termination provisions
5. Dispute resolution mechanisms
6. Enforceability concerns
""",
            'evidence_review': """
Review the following evidence document. Assess:
1. Relevance to potential legal issues
2. Admissibility considerations
3. Evidentiary weight
4. Potential authentication issues
5. Strategic use in litigation
"""
        }
        
        prompt = f"""
You are an expert legal document analyst. Review and analyze the following legal document.

ANALYSIS TYPE: {analysis_type.upper()}

{analysis_prompts.get(analysis_type, analysis_prompts['summary'])}

DOCUMENT CONTENT:
{document_content[:15000]}  # Limit content to avoid token limits
"""
        
        if specific_questions:
            prompt += f"""

ADDITIONAL QUESTIONS TO ADDRESS:
{specific_questions}
"""
        
        prompt += """

Please provide a thorough, professional analysis with specific references to the document content.
Structure your response with clear headings and bullet points for readability.
"""
        
        return prompt
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Simple approximation: ~4 characters per token
        return len(text) // 4


class DocumentAnalyzer:
    """
    Service class for analyzing legal documents.
    """
    
    def __init__(self):
        self.ai_service = GeminiAIService()
    
    def extract_text_from_document(self, document) -> str:
        """Extract text content from various document types."""
        try:
            file_content = document.file.read()
            file_extension = document.file_extension.lower()
            
            if file_extension == '.pdf':
                return self._extract_pdf_text(file_content)
            elif file_extension in ['.docx', '.doc']:
                return self._extract_docx_text(file_content)
            elif file_extension in ['.txt']:
                return file_content.decode('utf-8', errors='ignore')
            else:
                return "Unsupported document format for text extraction"
                
        except Exception as e:
            return f"Error extracting text: {str(e)}"
    
    def _extract_pdf_text(self, file_content: bytes) -> str:
        """Extract text from PDF file."""
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            return f"Error extracting PDF text: {str(e)}"
    
    def _extract_docx_text(self, file_content: bytes) -> str:
        """Extract text from DOCX file."""
        try:
            doc = DocxDocument(BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            return f"Error extracting DOCX text: {str(e)}"
    
    def analyze_documents(self, documents, analysis_type: str, specific_questions: str = "") -> str:
        """
        Analyze multiple documents and provide comprehensive analysis.
        
        Args:
            documents: QuerySet of Document objects
            analysis_type: Type of analysis required
            specific_questions: Specific questions about the documents
            
        Returns:
            Comprehensive analysis result
        """
        if not documents:
            return "No documents provided for analysis"
        
        analyses = []
        for doc in documents:
            try:
                text_content = self.extract_text_from_document(doc)
                analysis, _ = self.ai_service.analyze_document(
                    text_content, analysis_type, specific_questions
                )
                analyses.append({
                    'document_title': doc.title,
                    'file_name': doc.file_name,
                    'analysis': analysis
                })
            except Exception as e:
                analyses.append({
                    'document_title': doc.title,
                    'file_name': doc.file_name,
                    'analysis': f"Error analyzing document: {str(e)}"
                })
        
        # Combine analyses into comprehensive report
        combined_analysis = f"""
# Document Analysis Report

## Overview
Analyzed {len(documents)} document(s) using {analysis_type.replace('_', ' ').title()} analysis.

## Individual Document Analyses
"""
        
        for i, analysis in enumerate(analyses, 1):
            combined_analysis += f"""
### {i}. {analysis['document_title']}
**File:** {analysis['file_name']}

{analysis['analysis']}

---
"""
        
        if len(documents) > 1:
            combined_analysis += """
## Comparative Analysis
[This section would contain comparative analysis across multiple documents]

## Overall Recommendations
[This section would contain overall recommendations based on all documents]
"""
        
        return combined_analysis


class ResearchSessionManager:
    """
    Service class for managing research sessions.
    """
    
    @staticmethod
    def create_session_from_query(query):
        """Create a research session from an existing query."""
        from .models import ResearchSession
        
        session = ResearchSession.objects.create(
            title=f"Research Session for {query.title}",
            description=f"Research session created from query: {query.query[:100]}...",
            overall_objective=query.query,
            case=query.case,
            client=query.client,
            tenant=query.tenant,
            created_by=query.created_by
        )
        
        # Move query to session
        query.research_session = session
        query.save()
        
        return session
    
    @staticmethod
    def get_session_statistics(session):
        """Get comprehensive statistics for a research session."""
        queries = session.research_queries.all()
        
        return {
            'total_queries': queries.count(),
            'completed_queries': queries.filter(status='completed').count(),
            'failed_queries': queries.filter(status='failed').count(),
            'total_tokens': queries.aggregate(models.Sum('tokens_used'))['tokens_used__sum'] or 0,
            'average_processing_time': queries.aggregate(models.Avg('processing_time_seconds'))['processing_time_seconds__avg'] or 0,
            'query_types': queries.values('query_type').annotate(count=models.Count('id')),
        }
