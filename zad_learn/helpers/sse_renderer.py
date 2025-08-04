from rest_framework.renderers import BaseRenderer


class ServerSentEventRenderer(BaseRenderer):
    """
    Renderer for Server-Sent Events (SSE).
    """
    media_type = 'text/event-stream'
    format = 'sse'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render the data as a Server-Sent Event.
        """
        if isinstance(data, str):
            return data.encode(self.charset)
        return data 