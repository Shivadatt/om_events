from django.urls import path

from . import api

urlpatterns = [
    path("health", api.health),
    path("categories", api.categories),
    path("items", api.items),
    path("items/<slug:slug>", api.item_detail),
    path("reviews", api.reviews),
    path("leads", api.create_lead),
    path("quotes", api.create_quote),
    path("quotes/<str:public_id>/pdf", api.quote_pdf),
    path("auth/login", api.login),
    path("admin/stats", api.admin_stats),
]

