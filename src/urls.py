from blog.sitemap import BlogSitemap
from core.sitemap import MineralSitemap
from core.sitemap import PageSitemap
from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import index
from django.contrib.sitemaps.views import sitemap
from django.urls import include
from django.urls import path
from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.views import SpectacularRedocView
from drf_spectacular.views import SpectacularSwaggerView

sitemaps = {
    "page": PageSitemap,
    "blog": BlogSitemap,
    "mineral": MineralSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("_nested_admin/", include("nested_admin.urls")),
    path("", include("core.urls")),
    path("auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("blog/", include("blog.urls"), name="blog"),
    path("chem/", include("chem.urls"), name="chem"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("sitemap.xml", index, {"sitemaps": sitemaps, "sitemap_url_name": "sitemaps"}, name="sitemap"),
    path("sitemap-<section>.xml", sitemap, {"sitemaps": sitemaps}, name="sitemaps"),
]


if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
