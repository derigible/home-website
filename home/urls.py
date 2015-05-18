from django.conf.urls import patterns, include, url
from django.conf import settings
from .routes import routes
import sys

urlpatterns = patterns('',
    url(r'', include(routes.urls)),
)

# if 'linux' not in sys.platform.lower():
#     from django.conf.urls.static import static
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)