from django.apps import AppConfig


class ClientRequestsConfig(AppConfig):
    name = 'client_requests'
    verbose_name = 'Client Requests'
    
    def ready(self):
        """
        Initialize app when Django starts.
        """
        # No signals to import currently
        pass
