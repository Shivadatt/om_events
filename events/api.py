from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from io import BytesIO
import json
import re

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login as session_login
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .auth import admin_jwt_required, issue_access_token
from .models import Category, Customer, DecorationItem, Lead, Quotation, QuotationItem, Review
from .firebase_supabase import get_firestore_client

MONEY = Decimal("0.01")


def json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return None


def clean_text(value, maximum=500):
    return re.sub(r"[<>]", "", str(value or "")).strip()[:maximum]


def rate_limit(limit, seconds):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "unknown")).split(",")[0].strip()
            key = f"rate:{view.__name__}:{ip}"
            if cache.add(key, 1, seconds):
                count = 1
            else:
                try:
                    count = cache.incr(key)
                except ValueError:
                    cache.set(key, 1, seconds)
                    count = 1
            if count > limit:
                return JsonResponse({"error": "Too many requests. Please wait a moment and try again."}, status=429)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


@require_GET
def health(request):
    return JsonResponse({"status": "healthy", "service": "om-events-django"})


@require_GET
def categories(request):
    db = get_firestore_client()
    if db is not None:
        try:
            docs = db.collection("categories").where("is_active", "==", True).stream()
            data = []
            for doc in docs:
                # Handle both Admin SDK DocumentSnapshot and REST plain dicts
                if isinstance(doc, dict):
                    d = doc
                    d["id"] = doc.get("id") or doc.get("slug", "")
                else:
                    d = doc.to_dict()
                    d["id"] = doc.id
                # Count items belonging to this category
                items_docs = db.collection("items").where("category_id", "==", d["id"]).where("is_active", "==", True).stream()
                d["item_count"] = len(list(items_docs))
                data.append(d)
            if data:  # Only use Firestore result if it has data; otherwise fall through to SQLite
                data.sort(key=lambda x: (x.get("sort_order", 0), x.get("name", "")))
                return JsonResponse({"data": data})
        except Exception as e:
            # Fall back to local SQLite on error
            pass
            
    rows = Category.objects.filter(is_active=True).prefetch_related("items")
    return JsonResponse({"data": [row.to_dict() for row in rows]})


@require_GET
def items(request):
    category = clean_text(request.GET.get("category"), 140)
    search = clean_text(request.GET.get("q"), 120)
    theme = clean_text(request.GET.get("theme"), 80)
    featured = request.GET.get("featured")
    sort_param = request.GET.get("sort", "popular")
    
    try:
        per_page = min(max(int(request.GET.get("per_page", 24)), 1), 50)
        page_number = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        return JsonResponse({"error": "Pagination values must be numbers."}, status=422)

    db = get_firestore_client()
    if db is not None:
        try:
            ref = db.collection("items").where("is_active", "==", True)
            if category:
                ref = ref.where("category_id", "==", category)
            if featured == "true":
                ref = ref.where("is_featured", "==", True)
            
            cats_stream = db.collection("categories").stream()
            cat_names = {}
            for c in cats_stream:
                if isinstance(c, dict):
                    cat_names[c.get("id") or c.get("slug", "")] = c.get("name", "")
                else:
                    cat_names[c.id] = c.to_dict().get("name", "")

            docs = ref.stream()
            data = []
            for doc in docs:
                # Handle both Admin SDK DocumentSnapshot and REST plain dicts
                if isinstance(doc, dict):
                    d = doc
                    d["id"] = doc.get("id") or doc.get("slug", "")
                else:
                    d = doc.to_dict()
                    d["id"] = doc.id
                d["category_slug"] = d.get("category_id")
                d["category"] = cat_names.get(d.get("category_id"), "")
                d["effective_price"] = d.get("offer_price") if d.get("offer_price") is not None else d.get("price", 0)
                # Strip trailing whitespace from image_url
                if d.get("image_url"):
                    d["image_url"] = d["image_url"].strip()

                if search:
                    search_lower = search.lower()
                    text_match = (
                        search_lower in d.get("name", "").lower() or 
                        search_lower in d.get("description", "").lower() or 
                        any(search_lower in tag.lower() for tag in d.get("tags", []))
                    )
                    if not text_match:
                        continue
                if theme:
                    theme_lower = theme.lower()
                    if not any(theme_lower in t.lower() for t in d.get("themes", [])):
                        continue
                data.append(d)
            
            # Sorting
            if sort_param == "price_low":
                data.sort(key=lambda x: x.get("offer_price") if x.get("offer_price") is not None else x.get("price", 0))
            elif sort_param == "price_high":
                data.sort(key=lambda x: x.get("offer_price") if x.get("offer_price") is not None else x.get("price", 0), reverse=True)
            elif sort_param == "latest":
                data.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            else: # popular
                data.sort(key=lambda x: x.get("popularity", 0), reverse=True)
                
            # Manual pagination on sorted list
            total_count = len(data)
            if total_count > 0:  # Only use Firestore result if it has data; otherwise fall through to SQLite
                start_idx = (page_number - 1) * per_page
                end_idx = start_idx + per_page
                paginated_data = data[start_idx:end_idx]
                num_pages = (total_count + per_page - 1) // per_page
                return JsonResponse({
                    "data": paginated_data,
                    "meta": {"page": page_number, "pages": max(num_pages, 1), "total": total_count}
                })
        except Exception as e:
            # Fall back to local SQLite on error
            pass

    queryset = DecorationItem.objects.filter(is_active=True).select_related("category")
    if category:
        queryset = queryset.filter(category__slug=category)
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(description__icontains=search) |
            Q(tags__icontains=search) | Q(slug__icontains=search)
        )
    if theme:
        queryset = queryset.filter(themes__icontains=theme)
    if featured == "true":
        queryset = queryset.filter(is_featured=True)
        
    ordering = {"price_low": "offer_price", "price_high": "-offer_price", "latest": "-created_at", "popular": "-popularity"}.get(sort_param, "-popularity")
    queryset = queryset.order_by(ordering)
    page = Paginator(queryset, per_page).get_page(page_number)
    return JsonResponse({"data": [row.to_dict() for row in page.object_list],
                         "meta": {"page": page.number, "pages": page.paginator.num_pages, "total": page.paginator.count}})


@require_GET
def item_detail(request, slug):
    db = get_firestore_client()
    if db is not None:
        try:
            doc_ref = db.collection("items").document(slug)
            doc = doc_ref.get()
            if isinstance(doc, dict):
                # REST mode returns a dict directly from get()
                d = doc
                doc_exists = d is not None
            else:
                doc_exists = doc.exists
                d = doc.to_dict() if doc_exists else None

            if doc_exists and d:
                d["id"] = d.get("id") or slug
                # Fetch category name
                cat_doc = db.collection("categories").document(d.get("category_id", "")).get()
                if isinstance(cat_doc, dict):
                    cat_name = (cat_doc or {}).get("name", "")
                else:
                    cat_name = cat_doc.to_dict().get("name", "") if cat_doc.exists else ""

                d["category_slug"] = d.get("category_id")
                d["category"] = cat_name
                d["effective_price"] = d.get("offer_price") if d.get("offer_price") is not None else d.get("price", 0)
                if d.get("image_url"):
                    d["image_url"] = d["image_url"].strip()

                # Increment popularity
                doc_ref.update({"popularity": d.get("popularity", 0) + 1})
                return JsonResponse(d)
        except Exception:
            pass

    item = get_object_or_404(DecorationItem.objects.select_related("category"), slug=slug, is_active=True)
    DecorationItem.objects.filter(pk=item.pk).update(popularity=item.popularity + 1)
    return JsonResponse(item.to_dict())


@require_GET
def reviews(request):
    db = get_firestore_client()
    if db is not None:
        try:
            docs = db.collection("reviews").where("is_published", "==", True).limit(12).stream()
            data = []
            for doc in docs:
                d = doc.to_dict()
                data.append({
                    "customer_name": d.get("customer_name"),
                    "event_name": d.get("event_name"),
                    "rating": d.get("rating"),
                    "comment": d.get("comment"),
                    "image_url": d.get("image_url", ""),
                    "is_verified": d.get("is_verified", False),
                })
            return JsonResponse({"data": data})
        except Exception:
            pass

    rows = Review.objects.filter(is_published=True)[:12]
    return JsonResponse({"data": [row.to_dict() for row in rows]})


@csrf_exempt
@require_POST
@rate_limit(6, 60)
def create_lead(request):
    payload = json_body(request)
    if payload is None:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    if not clean_text(payload.get("name")) or not clean_text(payload.get("phone")):
        return JsonResponse({"error": "Name and phone are required."}, status=422)
    phone = re.sub(r"\D", "", str(payload["phone"]))[-10:]
    if len(phone) != 10:
        return JsonResponse({"error": "Enter a valid 10-digit phone number."}, status=422)
    event_date = None
    if payload.get("event_date"):
        try:
            event_date = date.fromisoformat(payload["event_date"])
        except (TypeError, ValueError):
            return JsonResponse({"error": "Event date must use YYYY-MM-DD."}, status=422)
    try:
        budget = Decimal(str(payload.get("budget") or 0))
    except InvalidOperation:
        budget = Decimal("0")

    db = get_firestore_client()
    if db is not None:
        try:
            lead_data = {
                "name": clean_text(payload["name"], 160),
                "phone": phone,
                "email": clean_text(payload.get("email"), 255),
                "request_type": clean_text(payload.get("request_type") or "callback", 50),
                "event_date": event_date.isoformat() if event_date else None,
                "budget": float(budget),
                "requirements": clean_text(payload.get("requirements"), 2000),
                "status": "new",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _, doc_ref = db.collection("leads").add(lead_data)
            return JsonResponse({"message": "Thanks — our celebration planner will call you shortly.", "lead_id": doc_ref.id}, status=201)
        except Exception as e:
            # Fall back to local SQLite on error
            pass

    lead = Lead.objects.create(
        name=clean_text(payload["name"], 160), phone=phone, email=clean_text(payload.get("email"), 255),
        request_type=clean_text(payload.get("request_type") or "callback", 50), event_date=event_date,
        budget=budget, requirements=clean_text(payload.get("requirements"), 2000),
    )
    return JsonResponse({"message": "Thanks — our celebration planner will call you shortly.", "lead_id": lead.pk}, status=201)


@csrf_exempt
@require_POST
@rate_limit(10, 60)
def create_quote(request):
    payload = json_body(request)
    if payload is None:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    missing = [field for field in ("name", "phone", "event_date", "location") if not clean_text(payload.get(field))]
    if missing:
        return JsonResponse({"error": f"Required fields: {', '.join(missing)}."}, status=422)
    raw_items = payload.get("items") or []
    if not isinstance(raw_items, list) or not raw_items:
        return JsonResponse({"error": "Choose at least one decoration."}, status=422)
    try:
        event_date = date.fromisoformat(payload["event_date"])
        event_time = datetime.strptime(payload.get("event_time") or "18:00", "%H:%M").time()
        requested_ids = [row.get("id") for row in raw_items]
    except (ValueError, TypeError):
        return JsonResponse({"error": "Choose a valid event date, time and decoration."}, status=422)
    if event_date < date.today():
        return JsonResponse({"error": "Event date cannot be in the past."}, status=422)
    phone = re.sub(r"\D", "", str(payload["phone"]))[-10:]
    if len(phone) != 10:
        return JsonResponse({"error": "Enter a valid 10-digit phone number."}, status=422)

    db = get_firestore_client()
    if db is not None:
        try:
            # Fetch products from Firestore
            products = {}
            for p_id in requested_ids:
                # In firestore, the document ID is the item slug (or we query it)
                doc = db.collection("items").document(str(p_id)).get()
                if doc.exists:
                    d = doc.to_dict()
                    d["id"] = doc.id
                    products[p_id] = d
                else:
                    # Let's try searching items by slug if not found directly
                    docs = db.collection("items").where("slug", "==", str(p_id)).limit(1).stream()
                    matched = list(docs)
                    if matched:
                        d = matched[0].to_dict()
                        d["id"] = matched[0].id
                        products[p_id] = d

            if len(products) != len(set(requested_ids)):
                return JsonResponse({"error": "One or more selected decorations are unavailable."}, status=409)

            subtotal, normalized = Decimal("0"), []
            for row in raw_items:
                product = products[row["id"]]
                try:
                    quantity = min(max(int(row.get("quantity", 1)), 1), 50)
                except (TypeError, ValueError):
                    return JsonResponse({"error": "Quantities must be numbers."}, status=422)
                effective_price = Decimal(str(product.get("offer_price") if product.get("offer_price") is not None else product.get("price")))
                subtotal += effective_price * quantity
                normalized.append({
                    "decoration_item_slug": product["slug"],
                    "name": product["name"],
                    "quantity": quantity,
                    "unit_price": float(effective_price),
                    "color": clean_text(row.get("color"), 80),
                    "theme": clean_text(row.get("theme"), 120),
                    "notes": clean_text(row.get("notes"), 500)
                })

            discount = (subtotal * Decimal("0.05") if subtotal >= Decimal("50000") else Decimal("0")).quantize(MONEY, rounding=ROUND_HALF_UP)
            delivery, travel = Decimal(str(settings.DELIVERY_CHARGE)), Decimal(str(settings.TRAVEL_CHARGE))
            gst_percent = Decimal(str(settings.GST_PERCENT))
            gst = ((subtotal - discount + delivery + travel) * gst_percent / 100).quantize(MONEY, rounding=ROUND_HALF_UP)
            grand_total = subtotal - discount + delivery + travel + gst

            # 2. Add or update customer
            cust_ref = db.collection("customers").document(phone)
            cust_doc = cust_ref.get()
            customer_name = clean_text(payload["name"], 160)
            customer_email = clean_text(payload.get("email"), 255)
            cust_data = {
                "name": customer_name,
                "phone": phone,
                "email": customer_email,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            if not cust_doc.exists:
                cust_data["created_at"] = datetime.now(timezone.utc).isoformat()
                cust_ref.set(cust_data)
            else:
                cust_ref.update({
                    "name": customer_name,
                    "email": customer_email,
                    "updated_at": cust_data["updated_at"]
                })

            from .models import generate_public_id
            public_id = generate_public_id()
            quote_data = {
                "public_id": public_id,
                "customer_name": customer_name,
                "customer_phone": phone,
                "event_date": event_date.isoformat(),
                "event_time": event_time.isoformat(),
                "location": clean_text(payload["location"], 500),
                "notes": clean_text(payload.get("notes"), 2000),
                "subtotal": float(subtotal),
                "discount": float(discount),
                "delivery_charge": float(delivery),
                "travel_charge": float(travel),
                "gst_percent": float(gst_percent),
                "gst_amount": float(gst),
                "grand_total": float(grand_total),
                "status": "draft",
                "items": normalized,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            db.collection("quotations").document(public_id).set(quote_data)

            return JsonResponse({"message": "Your quotation is ready.", "quotation": {
                "id": public_id, "public_id": public_id, "customer": customer_name, "phone": phone,
                "event_date": event_date.isoformat(), "location": quote_data["location"], "subtotal": float(subtotal),
                "discount": float(discount), "gst_amount": float(gst), "grand_total": float(grand_total),
                "status": "draft", "created_at": quote_data["created_at"]
            }, "pdf_url": f"/api/quotes/{public_id}/pdf"}, status=201)
        except Exception as e:
            # Fall back to local SQLite on error
            pass

    products = {p.pk: p for p in DecorationItem.objects.filter(pk__in=[int(x) for x in requested_ids if str(x).isdigit()], is_active=True)}
    if len(products) != len(set(requested_ids)):
        return JsonResponse({"error": "One or more selected decorations are unavailable."}, status=409)

    subtotal, normalized = Decimal("0"), []
    for row in raw_items:
        product = products[int(row["id"])]
        try:
            quantity = min(max(int(row.get("quantity", 1)), 1), 50)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Quantities must be numbers."}, status=422)
        subtotal += product.effective_price * quantity
        normalized.append((product, quantity, clean_text(row.get("color"), 80), clean_text(row.get("theme"), 120), clean_text(row.get("notes"), 500)))

    discount = (subtotal * Decimal("0.05") if subtotal >= Decimal("50000") else Decimal("0")).quantize(MONEY, rounding=ROUND_HALF_UP)
    delivery, travel = Decimal(str(settings.DELIVERY_CHARGE)), Decimal(str(settings.TRAVEL_CHARGE))
    gst_percent = Decimal(str(settings.GST_PERCENT))
    gst = ((subtotal - discount + delivery + travel) * gst_percent / 100).quantize(MONEY, rounding=ROUND_HALF_UP)
    grand_total = subtotal - discount + delivery + travel + gst

    with transaction.atomic():
        customer, _ = Customer.objects.get_or_create(phone=phone, defaults={"name": clean_text(payload["name"], 160)})
        customer.name, customer.email = clean_text(payload["name"], 160), clean_text(payload.get("email"), 255)
        customer.save(update_fields=["name", "email", "updated_at"])
        quote = Quotation.objects.create(
            customer=customer, event_date=event_date, event_time=event_time, location=clean_text(payload["location"], 500),
            notes=clean_text(payload.get("notes"), 2000), subtotal=subtotal, discount=discount,
            delivery_charge=delivery, travel_charge=travel, gst_percent=gst_percent, gst_amount=gst, grand_total=grand_total,
        )
        QuotationItem.objects.bulk_create([
            QuotationItem(quotation=quote, decoration_item=product, name=product.name, quantity=quantity,
                          unit_price=product.effective_price, color=color_name, theme=theme, notes=notes)
            for product, quantity, color_name, theme, notes in normalized
        ])
    return JsonResponse({"message": "Your quotation is ready.", "quotation": quote.to_dict(),
                         "pdf_url": f"/api/quotes/{quote.public_id}/pdf"}, status=201)


@require_GET
@rate_limit(30, 60)
def quote_pdf(request, public_id):
    db = get_firestore_client()
    quote = None
    if db is not None:
        try:
            doc = db.collection("quotations").document(public_id).get()
            if doc.exists:
                d = doc.to_dict()
                
                class DuckItem:
                    def __init__(self, data):
                        self.name = data["name"]
                        self.color = data.get("color", "")
                        self.theme = data.get("theme", "")
                        self.quantity = data["quantity"]
                        self.unit_price = Decimal(str(data["unit_price"]))

                class DuckCustomer:
                    def __init__(self, name):
                        self.name = name

                class DuckQuote:
                    def __init__(self, data):
                        self.public_id = data["public_id"]
                        self.event_date = date.fromisoformat(data["event_date"])
                        self.event_time = datetime.strptime(data["event_time"][:5], "%H:%M").time()
                        self.location = data["location"]
                        self.subtotal = Decimal(str(data["subtotal"]))
                        self.discount = Decimal(str(data["discount"]))
                        self.gst_percent = Decimal(str(data["gst_percent"]))
                        self.gst_amount = Decimal(str(data["gst_amount"]))
                        self.grand_total = Decimal(str(data["grand_total"]))
                        self.customer = DuckCustomer(data["customer_name"])
                        
                        class ItemsRel:
                            def __init__(self, items):
                                self._items = items
                            def all(self):
                                return self._items
                        self.items = ItemsRel([DuckItem(i) for i in data.get("items", [])])

                quote = DuckQuote(d)
        except Exception:
            pass

    if quote is None:
        quote = get_object_or_404(Quotation.objects.select_related("customer").prefetch_related("items"), public_id=public_id)
        
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Brand", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=25, leading=30, textColor=colors.HexColor("#9A6B3D")))
    story = [Paragraph(settings.BUSINESS_NAME.upper(), styles["Brand"]), Paragraph("CELEBRATION PROPOSAL", styles["Heading2"]), Spacer(1, 8),
             Paragraph(f"<b>Prepared for:</b> {quote.customer.name}<br/><b>Event:</b> {quote.event_date.strftime('%d %B %Y')} at {quote.event_time.strftime('%I:%M %p')}<br/><b>Location:</b> {quote.location}<br/><b>Quotation:</b> {quote.public_id.upper()}", styles["BodyText"]), Spacer(1, 16)]
    rows = [["Decoration", "Customisation", "Qty", "Amount"]]
    for row in quote.items.all():
        rows.append([row.name, " · ".join(filter(None, [row.color, row.theme])) or "As shown", str(row.quantity), f"Rs. {float(row.unit_price * row.quantity):,.0f}"])
    table = Table(rows, colWidths=[68*mm, 48*mm, 14*mm, 30*mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E2926")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D8D4CC")),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F4EE")]), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("PADDING", (0, 0), (-1, -1), 7), ("ALIGN", (2, 1), (-1, -1), "RIGHT")]))
    story.extend([table, Spacer(1, 14)])
    totals = [["Subtotal", f"Rs. {float(quote.subtotal):,.2f}"], ["Celebration discount", f"- Rs. {float(quote.discount):,.2f}"],
              [f"GST ({float(quote.gst_percent):g}%)", f"Rs. {float(quote.gst_amount):,.2f}"], ["GRAND TOTAL", f"Rs. {float(quote.grand_total):,.2f}"]]
    total_table = Table(totals, colWidths=[120*mm, 40*mm], hAlign="RIGHT")
    total_table.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor("#9A6B3D")),
                                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("PADDING", (0, 0), (-1, -1), 5)]))
    story.extend([total_table, Spacer(1, 20), Paragraph("This quotation is valid for 7 days and subject to date availability. Final execution is confirmed after advance payment.", styles["BodyText"]),
                   Spacer(1, 10), Paragraph(f"{settings.BUSINESS_EMAIL}  •  +{settings.BUSINESS_PHONE}", styles["BodyText"])])
    doc.build(story)
    stream.seek(0)
    return FileResponse(stream, as_attachment=True, filename=f"Om-Events-{quote.public_id}.pdf", content_type="application/pdf")


@csrf_exempt
@require_POST
@rate_limit(8, 60)
def login(request):
    payload = json_body(request) or {}
    email, password = clean_text(payload.get("email"), 255).lower(), str(payload.get("password") or "")
    User = get_user_model()
    user_record = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).first()
    user = authenticate(request, username=user_record.username, password=password) if user_record else None
    if not user or not user.is_active or not user.is_staff:
        return JsonResponse({"error": "Invalid email or password."}, status=401)
    session_login(request, user)
    return JsonResponse({"access_token": issue_access_token(user),
                         "user": {"name": user.get_full_name() or user.username, "email": user.email, "role": "admin"}})


@require_GET
@admin_jwt_required
def admin_stats(request):
    db = get_firestore_client()
    if db is not None:
        try:
            from .firebase_supabase import get_firebase_mode
            import logging
            api_logger = logging.getLogger(__name__)

            # If in Admin mode, perform optimized count & selection queries
            if get_firebase_mode() == "admin":
                leads_count = db.collection("leads").count().get()[0][0].value
                quotes_count = db.collection("quotations").count().get()[0][0].value
                cats_count = db.collection("categories").count().get()[0][0].value
                
                # Fetch only grand_total to compute revenue
                revenue_docs = db.collection("quotations").select(["grand_total"]).stream()
                revenue = sum(float(doc.to_dict().get("grand_total", 0.0)) for doc in revenue_docs)
                
                # Fetch only 8 recent leads sorted by created_at desc
                recent_leads_docs = db.collection("leads").order_by("created_at", direction="DESCENDING").limit(8).stream()
                # Fetch only 8 recent quotes sorted by created_at desc
                recent_quotes_docs = db.collection("quotations").order_by("created_at", direction="DESCENDING").limit(8).stream()
            else:
                # REST API or proxy mode fallback
                leads_docs = list(db.collection("leads").stream())
                quotes_docs = list(db.collection("quotations").stream())
                cats_docs = list(db.collection("categories").stream())
                
                leads_count = len(leads_docs)
                quotes_count = len(quotes_docs)
                cats_count = len(cats_docs)
                
                revenue = sum(float(doc.to_dict().get("grand_total", 0.0)) for doc in quotes_docs)
                
                recent_leads_docs = sorted(leads_docs, key=lambda x: x.to_dict().get("created_at", ""), reverse=True)[:8]
                recent_quotes_docs = sorted(quotes_docs, key=lambda x: x.to_dict().get("created_at", ""), reverse=True)[:8]

            recent_leads = []
            for doc in recent_leads_docs:
                d = doc.to_dict()
                recent_leads.append({
                    "id": doc.id,
                    "name": d.get("name", "Unknown"),
                    "phone": d.get("phone", ""),
                    "email": d.get("email", ""),
                    "request_type": d.get("request_type", "callback"),
                    "event_date": d.get("event_date"),
                    "status": d.get("status", "new"),
                    "created_at": d.get("created_at"),
                })
            
            recent_quotes = []
            for doc in recent_quotes_docs:
                d = doc.to_dict()
                recent_quotes.append({
                    "id": d.get("public_id"),
                    "public_id": d.get("public_id"),
                    "customer": d.get("customer_name", "Unknown"),
                    "event_date": d.get("event_date"),
                    "grand_total": d.get("grand_total", 0.0),
                    "status": d.get("status", "draft"),
                    "created_at": d.get("created_at"),
                })
            
            return JsonResponse({
                "leads": leads_count,
                "quotations": quotes_count,
                "revenue": revenue,
                "categories": cats_count,
                "recent_leads": recent_leads,
                "recent_quotes": recent_quotes,
            })
        except Exception as exc:
            api_logger.error("Error retrieving admin stats from Firestore: %s", exc, exc_info=True)
            pass

    revenue = Quotation.objects.aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
    return JsonResponse({
        "leads": Lead.objects.count(), "quotations": Quotation.objects.count(), "revenue": float(revenue),
        "categories": Category.objects.count(), "recent_leads": [row.to_dict() for row in Lead.objects.all()[:8]],
        "recent_quotes": [row.to_dict() for row in Quotation.objects.select_related("customer").all()[:8]],
    })
