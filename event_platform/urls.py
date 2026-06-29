from django.contrib import admin
from django.urls import include, path

from events import views

urlpatterns = [
    path("", views.home, name="home"),
    path("admin", views.studio, name="studio"),
    path("admin/", admin.site.urls),
    path("docs", views.docs, name="docs"),
    path("visual/<slug:slug>.svg", views.item_visual, name="item_visual"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", views.sitemap, name="sitemap"),
    path("api/", include("events.urls")),
]

handler404 = "events.views.error_404"
handler500 = "events.views.error_500"

