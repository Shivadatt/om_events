(() => {
  const state = { categories: [], items: [], cart: JSON.parse(localStorage.getItem("oe-cart") || "[]"), category: "", search: "", sort: "popular" };
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const money = value => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function api(url, options = {}) {
    const response = await fetch(url, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
    const data = response.headers.get("content-type")?.includes("json") ? await response.json() : null;
    if (!response.ok) throw new Error(data?.error || "Something went wrong. Please try again.");
    return data;
  }

  async function init() {
    bindUI();
    setupObservers();
    setDateMinimums();
    try {
      const [categories, items, reviews] = await Promise.all([api("/api/categories"), api("/api/items?per_page=30"), api("/api/reviews")]);
      state.categories = categories.data;
      state.items = items.data;
      hydrateCart();
      renderCategories();
      renderFilters();
      renderItems();
      renderReviews(reviews.data);
      updateCart();
    } catch (error) {
      $("#productGrid").innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
    }
  }

  function bindUI() {
    $("#cartOpen").addEventListener("click", openCart);
    $("#cartClose").addEventListener("click", closeCart);
    $("#drawerBackdrop").addEventListener("click", closeCart);
    $("#exploreButton").addEventListener("click", closeCart);
    $("#quoteButton").addEventListener("click", () => { closeCart(); $("#quoteModal").showModal(); });
    $("#searchInput").addEventListener("input", debounce(e => { state.search = e.target.value.trim(); loadItems(); }, 250));
    $("#sortSelect").addEventListener("change", e => { state.sort = e.target.value; loadItems(); });
    $("#themeToggle").addEventListener("click", toggleTheme);
    $("#menuButton").addEventListener("click", toggleMenu);
    $$("#header nav a").forEach(link => link.addEventListener("click", closeMenu));
    $$("[data-open-lead]").forEach(button => button.addEventListener("click", () => $("#leadModal").showModal()));
    $$("[data-close-modal]").forEach(button => button.addEventListener("click", () => button.closest("dialog").close()));
    $("#quoteForm").addEventListener("submit", submitQuote);
    $("#leadForm").addEventListener("submit", submitLead);
    window.addEventListener("scroll", () => $("#header").classList.toggle("fixed", scrollY > 120), { passive: true });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeCart(); });
  }

  function setupObservers() {
    const reveal = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add("visible"); reveal.unobserve(entry.target); }
    }), { threshold: .12 });
    $$(".reveal").forEach(el => reveal.observe(el));
    const counters = new IntersectionObserver(entries => entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const el = entry.target, end = Number(el.dataset.count), decimal = end % 1 !== 0;
      const start = performance.now();
      const tick = now => { const p = Math.min((now - start) / 1100, 1); el.textContent = (end * (1 - Math.pow(1 - p, 3))).toFixed(decimal ? 1 : 0); if (p < 1) requestAnimationFrame(tick); };
      requestAnimationFrame(tick); counters.unobserve(el);
    }), { threshold: .7 });
    $$("[data-count]").forEach(el => counters.observe(el));
  }

  function renderCategories() {
    $("#categoryGrid").innerHTML = state.categories.map(category => `
      <button class="category-card reveal visible" style="--card-color:${escapeHtml(category.color)}" data-category="${escapeHtml(category.slug)}">
        <span class="category-icon">${escapeHtml(category.icon)}</span>
        <div><small>${category.item_count} SIGNATURE EXPERIENCES</small><h3>${escapeHtml(category.name)}</h3><p>${escapeHtml(category.description)}</p></div><span class="arrow">↗</span>
      </button>`).join("");
    $$(".category-card").forEach(card => card.addEventListener("click", () => {
      state.category = card.dataset.category;
      renderFilters(); loadItems(); $("#experiences").scrollIntoView({ behavior: "smooth" });
    }));
  }

  function renderFilters() {
    $("#filterChips").innerHTML = `<button class="chip ${state.category ? "" : "active"}" data-category="">All</button>` +
      state.categories.map(c => `<button class="chip ${state.category === c.slug ? "active" : ""}" data-category="${c.slug}">${escapeHtml(c.name.replace(" Celebrations", ""))}</button>`).join("");
    $$(".chip").forEach(chip => chip.addEventListener("click", () => { state.category = chip.dataset.category; renderFilters(); loadItems(); }));
  }

  async function loadItems() {
    $("#productGrid").innerHTML = `<div class="skeleton product-skeleton"></div><div class="skeleton product-skeleton"></div><div class="skeleton product-skeleton"></div>`;
    try {
      const params = new URLSearchParams({ per_page: "30", sort: state.sort });
      if (state.category) params.set("category", state.category);
      if (state.search) params.set("q", state.search);
      const result = await api(`/api/items?${params}`);
      state.items = result.data;
      renderItems();
    } catch (error) { showToast(error.message); }
  }

  function renderItems() {
    $("#emptyState").classList.toggle("hidden", state.items.length > 0);
    $("#productGrid").innerHTML = state.items.map(item => {
      const offerPriceVal = item.discount_price ?? item.offer_price;
      const hasDiscount = offerPriceVal && offerPriceVal > 0 && offerPriceVal < item.price;
      
      return `
        <article class="product-card">
        <div class="product-image">
          <img src="${escapeHtml((item.image_url || '').trim())}" alt="${escapeHtml(item.name)} event setup" loading="lazy" width="600" height="480" onerror="this.onerror=null;this.src='/visual/${escapeHtml(item.slug)}.svg';">
          ${item.is_featured ? '<span class="product-badge">Most loved</span>' : ""}
          <button class="view-detail" data-detail="${escapeHtml(item.slug)}">View ${escapeHtml(item.name)}</button>
          <button class="quick-add" data-add="${item.id}" aria-label="Add ${escapeHtml(item.name)}">+</button>
        </div>
        <div class="product-info"><span class="product-meta">${escapeHtml(item.category)} · ${item.duration_hours} HRS</span><h3>${escapeHtml(item.name)}</h3>
          <p>${escapeHtml(item.description)}</p>
          <div class="product-foot">
            <div class="service-price">
              ${hasDiscount ? `
                <span class="offer-price">${money(offerPriceVal)}</span>
                <span class="original-price">${money(item.price)}</span>
              ` : `
                <span class="offer-price">${money(item.price)}</span>
              `}
            </div>
            <span class="rating">★ ${item.rating} (${item.total_reviews ?? item.review_count ?? 0})</span>
          </div>
        </div>
      </article>`;
    }).join("");
    $$("[data-add]").forEach(button => button.addEventListener("click", () => addToCart(Number(button.dataset.add))));
    $$("[data-detail]").forEach(button => button.addEventListener("click", () => openDetail(button.dataset.detail)));
  }

  function renderReviews(reviews) {
    $("#reviewsGrid").innerHTML = reviews.map(review => `<article class="review-card reveal visible"><span class="review-stars">${"★".repeat(review.rating)}</span><blockquote>“${escapeHtml(review.comment)}”</blockquote><div class="review-author"><b>${escapeHtml(review.customer_name)} ${review.is_verified ? "✓" : ""}</b><span>${escapeHtml(review.event_name)} · Verified celebration</span></div></article>`).join("");
  }

  function openDetail(slug) {
    const item = state.items.find(row => row.slug === slug);
    if (!item) return;
    const offerPriceVal = item.discount_price ?? item.offer_price;
    const hasDiscount = offerPriceVal && offerPriceVal > 0 && offerPriceVal < item.price;
    const discount = hasDiscount ? item.price - offerPriceVal : 0;
    const discountPercent = hasDiscount ? Math.round((discount / item.price) * 100) : 0;

    $("#detailContent").innerHTML = `<div class="detail-grid"><div class="detail-image"><img src="${escapeHtml((item.image_url || '').trim())}" alt="${escapeHtml(item.name)}" onerror="this.onerror=null;this.src='/visual/${escapeHtml(item.slug)}.svg';"></div>
      <div class="detail-info"><p class="eyebrow">${escapeHtml(item.category)} · CUSTOMIZABLE</p><h2>${escapeHtml(item.name)}</h2><p>${escapeHtml(item.description)}</p>
      <div class="detail-price-container" style="margin-bottom: 20px;">
        ${hasDiscount ? `
          <div class="price-original-row">
            <span class="price-original"><s>${money(item.price)}</s></span>
            <span class="price-badge">${discountPercent}% OFF</span>
          </div>
          <div class="price-offer-row">
            <span class="price-offer" style="font-size: 24px;">${money(offerPriceVal)}</span>
          </div>
          <div class="price-savings">You Save ${money(discount)}</div>
          <div class="price-starting">Starting Price</div>
        ` : `
          <div class="price-offer-row">
            <span class="price-offer" style="font-size: 24px;">${money(item.price)}</span>
          </div>
        `}
      </div>
      <div class="detail-options"><label>Color story<select id="detailColor">${item.colors.map(c => `<option>${escapeHtml(c)}</option>`).join("")}</select></label>
      <label>Design mood<select id="detailTheme">${item.themes.map(t => `<option>${escapeHtml(t)}</option>`).join("")}</select></label>
      <label>Your note<textarea id="detailNote" rows="3" placeholder="Names, venue details or a specific idea…"></textarea></label></div>
      <p class="detail-inclusions">✓ Styling & installation &nbsp; ✓ Teardown &nbsp; ✓ Dedicated coordinator</p>
      <button class="btn primary full" id="detailAdd">Add to my selection <span>↗</span></button></div></div>`;
    $("#detailAdd").addEventListener("click", () => {
      addToCart(item.id, { color: $("#detailColor").value, theme: $("#detailTheme").value, notes: $("#detailNote").value });
      $("#detailModal").close();
    });
    $("#detailModal").showModal();
  }

  function hydrateCart() {
    state.cart = state.cart.filter(row => {
      const product = state.items.find(item => item.id === row.id);
      if (product) row.product = product;
      return product;
    });
  }

  function addToCart(id, options = {}) {
    const product = state.items.find(item => item.id === id);
    if (!product) return;
    const existing = state.cart.find(row => row.id === id && row.color === (options.color || ""));
    if (existing) existing.quantity += 1;
    else state.cart.push({ id, quantity: 1, color: options.color || "", theme: options.theme || "", notes: options.notes || "", product });
    persistCart(); updateCart(); showToast(`${product.name} added to your selection`); openCart();
  }

  function updateCart() {
    const count = state.cart.reduce((sum, row) => sum + row.quantity, 0);
    $("#cartCount").textContent = count; $("#drawerCount").textContent = `(${count})`;
    $("#cartEmpty").classList.toggle("hidden", count > 0); $("#cartSummary").classList.toggle("hidden", count === 0);
    $("#cartItems").innerHTML = state.cart.map((row, index) => `<div class="cart-item"><img src="${escapeHtml(row.product.image_url)}" alt=""><div><h4>${escapeHtml(row.product.name)}</h4><small>${escapeHtml([row.color, row.theme].filter(Boolean).join(" · ") || "Customisable")}</small><b>${money(row.product.effective_price)}</b><div class="qty"><button data-minus="${index}" aria-label="Decrease">−</button><span>${row.quantity}</span><button data-plus="${index}" aria-label="Increase">+</button></div></div><button class="remove-item" data-remove="${index}" aria-label="Remove">×</button></div>`).join("");
    $$("[data-minus]").forEach(b => b.addEventListener("click", () => changeQuantity(Number(b.dataset.minus), -1)));
    $$("[data-plus]").forEach(b => b.addEventListener("click", () => changeQuantity(Number(b.dataset.plus), 1)));
    $$("[data-remove]").forEach(b => b.addEventListener("click", () => { state.cart.splice(Number(b.dataset.remove), 1); persistCart(); updateCart(); }));
    
// Calculate subtotal
const subtotal = state.cart.reduce(
    (sum, row) => sum + (row.product.effective_price * row.quantity),
    0
);

// Celebration discount
const discount = subtotal >= 50000 ? subtotal * 0.05 : 0;

// Delivery
const delivery = count > 0 ? 500 : 0;

// Amount after celebration discount
const taxable = subtotal - discount + delivery;

// GST
const gst = taxable * 0.18;

// Extra Discount = Delivery + GST
const extraDiscount = delivery + gst;

// Final Total
const grandTotal = taxable + gst - extraDiscount;

// Update UI
$("#subtotal").textContent = money(subtotal);

$("#discount").textContent =
    discount ? `− ${money(discount)}` : "Unlock at ₹50k";

$("#gst").textContent = money(gst);

$("#extraDiscount").textContent =
    `− ${money(extraDiscount)}`;

$("#grandTotal").textContent =
    money(grandTotal);
   
    
  }

  function changeQuantity(index, amount) {
    state.cart[index].quantity += amount;
    if (state.cart[index].quantity < 1) state.cart.splice(index, 1);
    persistCart(); updateCart();
  }
  function persistCart() { localStorage.setItem("oe-cart", JSON.stringify(state.cart.map(({ product, ...row }) => row))); }
  function openCart() { $("#cartDrawer").classList.add("open"); $("#drawerBackdrop").classList.add("open"); $("#cartDrawer").setAttribute("aria-hidden", "false"); document.body.classList.add("no-scroll"); }
  function closeCart() { $("#cartDrawer").classList.remove("open"); $("#drawerBackdrop").classList.remove("open"); $("#cartDrawer").setAttribute("aria-hidden", "true"); document.body.classList.remove("no-scroll"); }

  async function submitQuote(event) {
    event.preventDefault();
    const form = event.currentTarget, button = $("button[type=submit]", form), status = $("#quoteStatus");
    button.disabled = true; button.textContent = "Composing your quotation…"; status.textContent = "";
    const payload = Object.fromEntries(new FormData(form));
    payload.items = state.cart.map(({ product, ...row }) => row);
    try {
      const result = await api("/api/quotes", { method: "POST", body: JSON.stringify(payload) });
      status.className = "form-status success";
      status.innerHTML = `Quotation ${escapeHtml(result.quotation.public_id.toUpperCase())} is ready.`;
      button.textContent = "Download PDF";
      button.disabled = false; button.type = "button";
      button.onclick = () => { window.location.href = result.pdf_url; };
      state.cart = []; persistCart(); updateCart();
    } catch (error) { status.className = "form-status error"; status.textContent = error.message; button.disabled = false; button.innerHTML = 'Generate quotation <span>↗</span>'; }
  }

  async function submitLead(event) {
    event.preventDefault();
    const form = event.currentTarget, button = $("button[type=submit]", form), status = $("#leadStatus");
    button.disabled = true;
    try {
      const payload = Object.fromEntries(new FormData(form));
      const result = await api("/api/leads", { method: "POST", body: JSON.stringify(payload) });
      status.className = "form-status success"; status.textContent = result.message; form.reset(); setTimeout(() => $("#leadModal").close(), 1800);
    } catch (error) { status.className = "form-status error"; status.textContent = error.message; }
    finally { button.disabled = false; }
  }

  function toggleTheme() {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next; $("#themeToggle").textContent = next === "dark" ? "☀" : "☾"; localStorage.setItem("oe-theme", next);
  }
  function toggleMenu() {
    const open = $("#header").classList.toggle("mobile-open");
    $("#menuButton").textContent = open ? "Close" : "Menu";
    $("#menuButton").setAttribute("aria-expanded", String(open));
  }
  function closeMenu() {
    $("#header").classList.remove("mobile-open");
    $("#menuButton").textContent = "Menu";
    $("#menuButton").setAttribute("aria-expanded", "false");
  }
  function setDateMinimums() {
    const today = new Date().toISOString().split("T")[0];
    $$('input[type="date"]').forEach(input => input.min = today);
    const savedTheme = localStorage.getItem("oe-theme"); if (savedTheme) document.documentElement.dataset.theme = savedTheme;
  }
  function showToast(message) { const el = $("#toast"); el.textContent = message; el.classList.add("show"); setTimeout(() => el.classList.remove("show"), 2600); }
  function debounce(fn, wait) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); }; }
  init();
})();
