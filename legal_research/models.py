from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import json

User = get_user_model()


class LegalResearchQuery(models.Model):
    """
    Model representing a legal research query made by a lawyer.
    """
    QUERY_TYPE_CHOICES = [
        ('case_law', 'Case Law Research'),
        ('statute', 'Statute Research'),
        ('regulation', 'Regulation Research'),
        ('legal_analysis', 'Legal Analysis'),
        ('document_review', 'Document Review'),
        ('contract_analysis', 'Contract Analysis'),
        ('precedent', 'Precedent Search'),
        ('legal_argument', 'Legal Argument Development'),
        ('other', 'Other Research'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Query Information
    title = models.CharField(max_length=255)
    query = models.TextField(help_text="The legal research question or topic")
    query_type = models.CharField(max_length=20, choices=QUERY_TYPE_CHOICES, default='case_law')
    
    # Context Information
    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='research_queries'
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='research_queries'
    )
    documents = models.ManyToManyField(
        'documents.Document',
        blank=True,
        related_name='research_queries'
    )
    
    # Additional Context
    jurisdiction = models.CharField(
        max_length=100,
        blank=True,
        help_text="Jurisdiction for the research (e.g., Federal, California, New York)"
    )
    practice_area = models.CharField(
        max_length=100,
        blank=True,
        help_text="Practice area (e.g., Corporate Law, Family Law, Criminal Law)"
    )
    relevant_facts = models.TextField(
        blank=True,
        help_text="Relevant facts for the research context"
    )
    specific_requirements = models.TextField(
        blank=True,
        help_text="Any specific requirements or constraints for the research"
    )
    
    # AI Processing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    ai_response = models.TextField(blank=True, null=True)
    ai_model_used = models.CharField(max_length=50, default='gemini-flash')
    tokens_used = models.PositiveIntegerField(default=0)
    processing_time_seconds = models.PositiveIntegerField(default=0)
    
    # Quality Assessment
    relevance_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="AI-assessed relevance score (0.00-1.00)"
    )
    confidence_level = models.CharField(
        max_length=20,
        choices=[
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
        ],
        blank=True,
        help_text="AI confidence level in the response"
    )
    
    # User Feedback
    user_rating = models.IntegerField(
        null=True,
        blank=True,
        choices=[(i, i) for i in range(1, 6)],
        help_text="User rating (1-5 stars)"
    )
    user_feedback = models.TextField(
        blank=True,
        help_text="User feedback on the research result"
    )
    is_helpful = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether the user found the response helpful"
    )
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='research_queries'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='research_queries'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'legal_research_queries'
        verbose_name = 'Legal Research Query'
        verbose_name_plural = 'Legal Research Queries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_by']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'query_type']),
            models.Index(fields=['case']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_query_type_display()}"
    
    @property
    def is_completed(self):
        """Check if the query is completed."""
        return self.status == 'completed'
    
    @property
    def is_processing(self):
        """Check if the query is currently being processed."""
        return self.status == 'processing'
    
    def mark_completed(self, ai_response, tokens_used=0, processing_time=0):
        """Mark the query as completed with AI response."""
        self.status = 'completed'
        self.ai_response = ai_response
        self.tokens_used = tokens_used
        self.processing_time_seconds = processing_time
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, error_message):
        """Mark the query as failed."""
        self.status = 'failed'
        self.ai_response = f"Error: {error_message}"
        self.completed_at = timezone.now()
        self.save()


class ResearchSource(models.Model):
    """
    Model representing sources cited in legal research responses.
    """
    SOURCE_TYPE_CHOICES = [
        ('case_law', 'Case Law'),
        ('statute', 'Statute'),
        ('regulation', 'Regulation'),
        ('secondary_source', 'Secondary Source'),
        ('court_rule', 'Court Rule'),
        ('treatise', 'Legal Treatise'),
        ('law_review', 'Law Review Article'),
        ('other', 'Other'),
    ]
    
    # Source Information
    title = models.CharField(max_length=500)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    citation = models.TextField(help_text="Full legal citation")
    url = models.URLField(blank=True, null=True)
    
    # Content Summary
    summary = models.TextField(help_text="Brief summary of the source content")
    relevance_explanation = models.TextField(
        help_text="Explanation of why this source is relevant to the query"
    )
    
    # Metadata
    jurisdiction = models.CharField(max_length=100, blank=True)
    decision_date = models.DateField(null=True, blank=True)
    court = models.CharField(max_length=200, blank=True)
    
    # Relationship to Query
    research_query = models.ForeignKey(
        LegalResearchQuery,
        on_delete=models.CASCADE,
        related_name='sources'
    )
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='research_sources'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'research_sources'
        verbose_name = 'Research Source'
        verbose_name_plural = 'Research Sources'
        ordering = ['source_type', 'title']
        indexes = [
            models.Index(fields=['tenant', 'research_query']),
            models.Index(fields=['source_type']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_source_type_display()})"


class ResearchSession(models.Model):
    """
    Model representing a research session that may contain multiple related queries.
    """
    # Session Information
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Session Context
    overall_objective = models.TextField(help_text="Overall objective of the research session")
    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='research_sessions'
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='research_sessions'
    )
    
    # Session Metadata
    queries_count = models.PositiveIntegerField(default=0)
    total_tokens_used = models.PositiveIntegerField(default=0)
    total_processing_time = models.PositiveIntegerField(default=0)
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='research_sessions'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='research_sessions'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'research_sessions'
        verbose_name = 'Research Session'
        verbose_name_plural = 'Research Sessions'
        ordering = ['-last_activity_at']
        indexes = [
            models.Index(fields=['tenant', 'created_by']),
            models.Index(fields=['case']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.created_at.strftime('%Y-%m-%d')}"
    
    def update_statistics(self):
        """Update session statistics based on associated queries."""
        queries = self.research_queries.all()
        self.queries_count = queries.count()
        self.total_tokens_used = sum(q.tokens_used for q in queries if q.tokens_used)
        self.total_processing_time = sum(q.processing_time_seconds for q in queries if q.processing_time_seconds)
        self.save()
