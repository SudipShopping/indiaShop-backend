"""
app.py – IndiaShop Flask Backend
Routes:
  Auth   : POST /api/auth/register  /api/auth/verify-otp  /api/auth/login
           POST /api/auth/forgot-password  /api/auth/reset-password
           POST /api/auth/refresh          GET  /api/auth/me
  Users  : GET/PUT /api/users/profile      GET/POST/DELETE /api/users/addresses
  Products: GET /api/products  /api/products/<slug>
            POST/PUT/DELETE (admin) /api/admin/products
  Categories: GET /api/categories
  Cart   : GET/POST /api/cart   PUT/DELETE /api/cart/<item_id>
  Orders : POST /api/orders  GET /api/orders  GET /api/orders/<id>
           PATCH /api/admin/orders/<id>/status
  Reviews: POST /api/products/<slug>/reviews
"""

import os
import random
import string
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, g
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, verify_jwt_in_request,
)
from flask_cors import CORS

from config import config_map
from models import (
    db, User, OTP, Category, Product, ProductImage,
    Cart, CartItem, Address, Order, OrderItem, Review,
)
from email import (
    send_otp_email_sync, send_reset_email_sync,
    send_order_confirmation_sync, send_order_status_update_sync,
)


# ─────────────────────────────────────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────────────────────────────────────
def create_app(env: str = "default") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_map[env])

    # Extensions
    db.init_app(app)
    JWTManager(app)
    CORS(app, origins=app.config["CORS_ORIGINS"])

    with app.app_context():
        db.create_all()
        _seed_categories(app)

    # Blueprints / route registration
    _register_routes(app)
    return app


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _gen_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _ok(data=None, msg: str = "success", status: int = 200):
    body = {"success": True, "message": msg}
    if data is not None:
        body["data"] = data
    return jsonify(body), status


def _err(msg: str = "error", status: int = 400):
    return jsonify({"success": False, "message": msg}), status


def _current_user() -> User | None:
    try:
        verify_jwt_in_request()
        uid = get_jwt_identity()
        return User.query.get(uid)
    except Exception:
        return None


def _require_admin():
    user = _current_user()
    if not user or user.role != "admin":
        return _err("Admin access required", 403)
    return user


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Seed default categories (matches the frontend)
# ─────────────────────────────────────────────────────────────────────────────
def _seed_categories(app: Flask):
    cats = [
        ("Electronics", "electronics", "📱"),
        ("Fashion",     "fashion",     "👗"),
        ("Home",        "home",        "🏠"),
        ("Beauty",      "beauty",      "💄"),
        ("Sports",      "sports",      "⚽"),
        ("Books",       "books",       "📚"),
        ("Toys",        "toys",        "🎮"),
        ("Appliances",  "appliances",  "🔌"),
    ]
    for name, slug, emoji in cats:
        if not Category.query.filter_by(slug=slug).first():
            db.session.add(Category(name=name, slug=slug, emoji=emoji))
    db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Route registration
# ─────────────────────────────────────────────────────────────────────────────
def _register_routes(app: Flask):

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/api/health")
    def health():
        return _ok({"status": "ok", "app": "indiaShop"})

    # =========================================================================
    # AUTH
    # =========================================================================
    @app.post("/api/auth/register")
    def register():
        data = request.get_json() or {}
        name  = (data.get("name")  or "").strip()
        email = (data.get("email") or "").strip().lower()
        pwd   = data.get("password", "")

        if not name or not email or not pwd:
            return _err("name, email and password are required")
        if len(pwd) < 6:
            return _err("Password must be at least 6 characters")
        if User.query.filter_by(email=email).first():
            return _err("Email already registered")

        user = User(name=name, email=email)
        user.set_password(pwd)
        db.session.add(user)
        db.session.commit()

        # Create cart for user
        db.session.add(Cart(user_id=user.id))
        db.session.commit()

        # Send OTP
        otp_code = _gen_otp()
        expires  = datetime.utcnow() + timedelta(minutes=app.config["OTP_EXPIRE_MINUTES"])
        db.session.add(OTP(user_id=user.id, code=otp_code, purpose="verify_email", expires_at=expires))
        db.session.commit()

        try:
            send_otp_email_sync(email, otp_code, "verify your indiaShop account")
        except Exception as e:
            app.logger.error(f"OTP email failed: {e}")

        return _ok({"user_id": user.id}, "Registered! Check email for OTP.", 201)


    @app.post("/api/auth/verify-otp")
    def verify_otp():
        data    = request.get_json() or {}
        email   = (data.get("email") or "").strip().lower()
        code    = (data.get("otp")   or "").strip()
        purpose = data.get("purpose", "verify_email")

        user = User.query.filter_by(email=email).first()
        if not user:
            return _err("User not found", 404)

        otp = OTP.query.filter_by(user_id=user.id, code=code, purpose=purpose)\
                       .order_by(OTP.created_at.desc()).first()
        if not otp or not otp.is_valid():
            return _err("Invalid or expired OTP")

        otp.is_used = True
        if purpose == "verify_email":
            user.is_verified = True
        db.session.commit()

        access  = create_access_token(identity=user.id)
        refresh = create_refresh_token(identity=user.id)
        return _ok({"access_token": access, "refresh_token": refresh, "user": user.to_dict()},
                   "OTP verified")


    @app.post("/api/auth/login")
    def login():
        data  = request.get_json() or {}
        email = (data.get("email")    or "").strip().lower()
        pwd   = data.get("password", "")

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(pwd):
            return _err("Invalid email or password", 401)
        if not user.is_active:
            return _err("Account is deactivated", 403)

        access  = create_access_token(identity=user.id)
        refresh = create_refresh_token(identity=user.id)
        return _ok({"access_token": access, "refresh_token": refresh, "user": user.to_dict()})


    @app.post("/api/auth/refresh")
    @jwt_required(refresh=True)
    def refresh_token():
        uid    = get_jwt_identity()
        access = create_access_token(identity=uid)
        return _ok({"access_token": access})


    @app.get("/api/auth/me")
    @jwt_required()
    def me():
        user = User.query.get(get_jwt_identity())
        if not user:
            return _err("User not found", 404)
        return _ok(user.to_dict())


    @app.post("/api/auth/forgot-password")
    def forgot_password():
        data  = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        user  = User.query.filter_by(email=email).first()
        if not user:
            return _ok(msg="If email exists, OTP has been sent")   # security: no leak

        otp_code = _gen_otp()
        expires  = datetime.utcnow() + timedelta(minutes=app.config["OTP_EXPIRE_MINUTES"])
        db.session.add(OTP(user_id=user.id, code=otp_code, purpose="reset_password", expires_at=expires))
        db.session.commit()

        try:
            send_reset_email_sync(email, otp_code)
        except Exception as e:
            app.logger.error(f"Reset email failed: {e}")

        return _ok(msg="If email exists, OTP has been sent")


    @app.post("/api/auth/reset-password")
    def reset_password():
        data     = request.get_json() or {}
        email    = (data.get("email")    or "").strip().lower()
        code     = (data.get("otp")      or "").strip()
        new_pwd  = data.get("password",  "")

        if len(new_pwd) < 6:
            return _err("Password must be at least 6 characters")

        user = User.query.filter_by(email=email).first()
        if not user:
            return _err("User not found", 404)

        otp = OTP.query.filter_by(user_id=user.id, code=code, purpose="reset_password")\
                       .order_by(OTP.created_at.desc()).first()
        if not otp or not otp.is_valid():
            return _err("Invalid or expired OTP")

        otp.is_used = True
        user.set_password(new_pwd)
        db.session.commit()
        return _ok(msg="Password reset successful")


    # =========================================================================
    # USER PROFILE & ADDRESSES
    # =========================================================================
    @app.get("/api/users/profile")
    @jwt_required()
    def get_profile():
        user = User.query.get(get_jwt_identity())
        return _ok(user.to_dict())


    @app.put("/api/users/profile")
    @jwt_required()
    def update_profile():
        user = User.query.get(get_jwt_identity())
        data = request.get_json() or {}
        if "name"  in data: user.name  = data["name"].strip()
        if "phone" in data: user.phone = data["phone"].strip()
        if "password" in data:
            if len(data["password"]) < 6:
                return _err("Password too short")
            user.set_password(data["password"])
        db.session.commit()
        return _ok(user.to_dict(), "Profile updated")


    @app.get("/api/users/addresses")
    @jwt_required()
    def get_addresses():
        user = User.query.get(get_jwt_identity())
        return _ok([a.to_dict() for a in user.addresses])


    @app.post("/api/users/addresses")
    @jwt_required()
    def add_address():
        user = User.query.get(get_jwt_identity())
        data = request.get_json() or {}
        required = ["full_name", "phone", "line1", "city", "state", "pincode"]
        if any(not data.get(f) for f in required):
            return _err(f"Required: {', '.join(required)}")

        if data.get("is_default"):
            for a in user.addresses:
                a.is_default = False

        addr = Address(
            user_id   = user.id,
            full_name = data["full_name"].strip(),
            phone     = data["phone"].strip(),
            line1     = data["line1"].strip(),
            line2     = data.get("line2", "").strip(),
            city      = data["city"].strip(),
            state     = data["state"].strip(),
            pincode   = data["pincode"].strip(),
            country   = data.get("country", "India"),
            is_default= bool(data.get("is_default", False)),
        )
        db.session.add(addr)
        db.session.commit()
        return _ok(addr.to_dict(), "Address added", 201)


    @app.delete("/api/users/addresses/<int:addr_id>")
    @jwt_required()
    def delete_address(addr_id):
        user = User.query.get(get_jwt_identity())
        addr = Address.query.filter_by(id=addr_id, user_id=user.id).first()
        if not addr:
            return _err("Address not found", 404)
        db.session.delete(addr)
        db.session.commit()
        return _ok(msg="Address deleted")


    # =========================================================================
    # CATEGORIES
    # =========================================================================
    @app.get("/api/categories")
    def get_categories():
        cats = Category.query.filter_by(is_active=True).all()
        return _ok([c.to_dict() for c in cats])


    # =========================================================================
    # PRODUCTS
    # =========================================================================
    @app.get("/api/products")
    def get_products():
        category  = request.args.get("category")
        search    = request.args.get("search", "").strip()
        sort      = request.args.get("sort", "newest")       # newest | rating | price_asc | price_desc
        featured  = request.args.get("featured")
        page      = int(request.args.get("page", 1))
        limit     = int(request.args.get("limit", app.config["PRODUCTS_PER_PAGE"]))

        q = Product.query.filter_by(is_active=True)

        if category:
            cat = Category.query.filter(
                (Category.slug == category) | (Category.name == category)
            ).first()
            if cat:
                q = q.filter_by(category_id=cat.id)

        if search:
            q = q.filter(
                Product.name.ilike(f"%{search}%") |
                Product.brand.ilike(f"%{search}%") |
                Product.description.ilike(f"%{search}%")
            )

        if featured == "true":
            q = q.filter_by(is_featured=True)

        if sort == "price_asc":
            q = q.order_by(Product.price.asc())
        elif sort == "price_desc":
            q = q.order_by(Product.price.desc())
        elif sort == "rating":
            q = q.order_by(Product.created_at.desc())   # avg_rating computed in Python
        else:
            q = q.order_by(Product.created_at.desc())

        total    = q.count()
        products = q.offset((page - 1) * limit).limit(limit).all()

        if sort == "rating":
            products.sort(key=lambda p: p.avg_rating, reverse=True)

        return _ok({
            "products":    [p.to_dict() for p in products],
            "total":       total,
            "page":        page,
            "limit":       limit,
            "total_pages": (total + limit - 1) // limit,
        })


    @app.get("/api/products/<slug>")
    def get_product(slug):
        product = Product.query.filter_by(slug=slug, is_active=True).first()
        if not product:
            return _err("Product not found", 404)
        return _ok(product.to_dict(detail=True))


    # ── Admin: create product ─────────────────────────────────────────────────
    @app.post("/api/admin/products")
    @jwt_required()
    def create_product():
        result = _require_admin()
        if isinstance(result, tuple):
            return result

        data = request.get_json() or {}
        required = ["name", "price", "category_id"]
        if any(not data.get(f) for f in required):
            return _err(f"Required: {', '.join(required)}")

        slug = _slugify(data["name"])
        if Product.query.filter_by(slug=slug).first():
            slug = f"{slug}-{random.randint(100, 999)}"

        product = Product(
            category_id  = data["category_id"],
            name         = data["name"].strip(),
            slug         = slug,
            description  = data.get("description", ""),
            price        = data["price"],
            discount_pct = int(data.get("discount_pct", 0)),
            stock        = int(data.get("stock", 0)),
            sku          = data.get("sku"),
            brand        = data.get("brand", ""),
            is_featured  = bool(data.get("is_featured", False)),
        )
        db.session.add(product)
        db.session.flush()

        for img in data.get("images", []):
            db.session.add(ProductImage(
                product_id = product.id,
                url        = img.get("url", ""),
                alt_text   = img.get("alt_text", product.name),
                is_primary = img.get("is_primary", False),
            ))

        db.session.commit()
        return _ok(product.to_dict(detail=True), "Product created", 201)


    @app.put("/api/admin/products/<int:pid>")
    @jwt_required()
    def update_product(pid):
        result = _require_admin()
        if isinstance(result, tuple):
            return result

        product = Product.query.get(pid)
        if not product:
            return _err("Product not found", 404)

        data = request.get_json() or {}
        fields = ["name", "description", "price", "discount_pct", "stock",
                  "sku", "brand", "is_active", "is_featured", "category_id"]
        for f in fields:
            if f in data:
                setattr(product, f, data[f])

        db.session.commit()
        return _ok(product.to_dict(detail=True), "Product updated")


    @app.delete("/api/admin/products/<int:pid>")
    @jwt_required()
    def delete_product(pid):
        result = _require_admin()
        if isinstance(result, tuple):
            return result

        product = Product.query.get(pid)
        if not product:
            return _err("Product not found", 404)
        product.is_active = False   # soft delete
        db.session.commit()
        return _ok(msg="Product deactivated")


    # =========================================================================
    # CART
    # =========================================================================
    @app.get("/api/cart")
    @jwt_required()
    def get_cart():
        user = User.query.get(get_jwt_identity())
        cart = user.cart or Cart(user_id=user.id)
        if not user.cart:
            db.session.add(cart)
            db.session.commit()
        return _ok(cart.to_dict())


    @app.post("/api/cart")
    @jwt_required()
    def add_to_cart():
        user = User.query.get(get_jwt_identity())
        data = request.get_json() or {}
        pid  = data.get("product_id")
        qty  = int(data.get("quantity", 1))

        if not pid:
            return _err("product_id is required")
        if qty < 1:
            return _err("quantity must be >= 1")

        product = Product.query.filter_by(id=pid, is_active=True).first()
        if not product:
            return _err("Product not found", 404)
        if product.stock < qty:
            return _err(f"Only {product.stock} units in stock")

        cart = user.cart
        if not cart:
            cart = Cart(user_id=user.id)
            db.session.add(cart)
            db.session.flush()

        item = CartItem.query.filter_by(cart_id=cart.id, product_id=pid).first()
        if item:
            new_qty = item.quantity + qty
            if product.stock < new_qty:
                return _err(f"Only {product.stock} units in stock")
            item.quantity = new_qty
        else:
            db.session.add(CartItem(cart_id=cart.id, product_id=pid, quantity=qty))

        db.session.commit()
        return _ok(cart.to_dict(), "Added to cart")


    @app.put("/api/cart/<int:item_id>")
    @jwt_required()
    def update_cart_item(item_id):
        user = User.query.get(get_jwt_identity())
        data = request.get_json() or {}
        qty  = int(data.get("quantity", 1))

        item = CartItem.query.join(Cart).filter(
            CartItem.id == item_id, Cart.user_id == user.id
        ).first()
        if not item:
            return _err("Cart item not found", 404)

        if qty < 1:
            db.session.delete(item)
        else:
            if item.product.stock < qty:
                return _err(f"Only {item.product.stock} units in stock")
            item.quantity = qty

        db.session.commit()
        return _ok(user.cart.to_dict(), "Cart updated")


    @app.delete("/api/cart/<int:item_id>")
    @jwt_required()
    def remove_cart_item(item_id):
        user = User.query.get(get_jwt_identity())
        item = CartItem.query.join(Cart).filter(
            CartItem.id == item_id, Cart.user_id == user.id
        ).first()
        if not item:
            return _err("Cart item not found", 404)
        db.session.delete(item)
        db.session.commit()
        return _ok(user.cart.to_dict(), "Item removed")


    @app.delete("/api/cart")
    @jwt_required()
    def clear_cart():
        user = User.query.get(get_jwt_identity())
        if user.cart:
            CartItem.query.filter_by(cart_id=user.cart.id).delete()
            db.session.commit()
        return _ok(msg="Cart cleared")


    # =========================================================================
    # ORDERS
    # =========================================================================
    @app.post("/api/orders")
    @jwt_required()
    def place_order():
        user = User.query.get(get_jwt_identity())
        data = request.get_json() or {}

        addr_id        = data.get("address_id")
        payment_method = data.get("payment_method", "cod")

        if not addr_id:
            return _err("address_id is required")

        addr = Address.query.filter_by(id=addr_id, user_id=user.id).first()
        if not addr:
            return _err("Address not found", 404)

        cart = user.cart
        if not cart or not cart.items:
            return _err("Cart is empty")

        # Check stock for all items
        for ci in cart.items:
            if ci.product.stock < ci.quantity:
                return _err(f"'{ci.product.name}' has only {ci.product.stock} units in stock")

        # Create order
        order = Order(
            user_id        = user.id,
            address_id     = addr.id,
            payment_method = payment_method,
            total_amount   = cart.total,
            notes          = data.get("notes", ""),
        )
        db.session.add(order)
        db.session.flush()

        for ci in cart.items:
            db.session.add(OrderItem(
                order_id   = order.id,
                product_id = ci.product_id,
                quantity   = ci.quantity,
                unit_price = ci.product.discounted_price,
            ))
            ci.product.stock -= ci.quantity

        # Clear cart
        CartItem.query.filter_by(cart_id=cart.id).delete()
        db.session.commit()

        # Send confirmation email
        try:
            send_order_confirmation_sync(user.email, order)
        except Exception as e:
            app.logger.error(f"Order confirm email failed: {e}")

        return _ok(order.to_dict(detail=True), "Order placed successfully!", 201)


    @app.get("/api/orders")
    @jwt_required()
    def get_orders():
        user   = User.query.get(get_jwt_identity())
        orders = Order.query.filter_by(user_id=user.id)\
                            .order_by(Order.created_at.desc()).all()
        return _ok([o.to_dict() for o in orders])


    @app.get("/api/orders/<int:order_id>")
    @jwt_required()
    def get_order(order_id):
        user  = User.query.get(get_jwt_identity())
        order = Order.query.filter_by(id=order_id, user_id=user.id).first()
        if not order:
            return _err("Order not found", 404)
        return _ok(order.to_dict(detail=True))


    @app.delete("/api/orders/<int:order_id>")
    @jwt_required()
    def cancel_order(order_id):
        user  = User.query.get(get_jwt_identity())
        order = Order.query.filter_by(id=order_id, user_id=user.id).first()
        if not order:
            return _err("Order not found", 404)
        if order.status not in ("pending", "confirmed"):
            return _err("Order cannot be cancelled at this stage")

        # Restore stock
        for item in order.items:
            item.product.stock += item.quantity

        order.status = "cancelled"
        db.session.commit()

        try:
            send_order_status_update_sync(user.email, order.id, "cancelled", user.name)
        except Exception as e:
            app.logger.error(f"Cancel email failed: {e}")

        return _ok(msg="Order cancelled")


    # ── Admin: update order status ─────────────────────────────────────────────
    @app.patch("/api/admin/orders/<int:order_id>/status")
    @jwt_required()
    def update_order_status(order_id):
        result = _require_admin()
        if isinstance(result, tuple):
            return result

        order = Order.query.get(order_id)
        if not order:
            return _err("Order not found", 404)

        data   = request.get_json() or {}
        status = data.get("status", "")
        valid  = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
        if status not in valid:
            return _err(f"status must be one of: {', '.join(valid)}")

        order.status = status
        db.session.commit()

        try:
            send_order_status_update_sync(
                order.user.email, order.id, status, order.user.name
            )
        except Exception as e:
            app.logger.error(f"Status email failed: {e}")

        return _ok(order.to_dict(detail=True), "Order status updated")


    # ── Admin: all orders ──────────────────────────────────────────────────────
    @app.get("/api/admin/orders")
    @jwt_required()
    def admin_get_orders():
        result = _require_admin()
        if isinstance(result, tuple):
            return result

        page   = int(request.args.get("page", 1))
        limit  = int(request.args.get("limit", 20))
        status = request.args.get("status")

        q = Order.query.order_by(Order.created_at.desc())
        if status:
            q = q.filter_by(status=status)

        total  = q.count()
        orders = q.offset((page - 1) * limit).limit(limit).all()
        return _ok({
            "orders":      [o.to_dict(detail=True) for o in orders],
            "total":       total,
            "page":        page,
            "total_pages": (total + limit - 1) // limit,
        })


    # =========================================================================
    # REVIEWS
    # =========================================================================
    @app.post("/api/products/<slug>/reviews")
    @jwt_required()
    def add_review(slug):
        user    = User.query.get(get_jwt_identity())
        product = Product.query.filter_by(slug=slug, is_active=True).first()
        if not product:
            return _err("Product not found", 404)

        # Check: user must have bought the product
        bought = OrderItem.query.join(Order).filter(
            Order.user_id    == user.id,
            Order.status     == "delivered",
            OrderItem.product_id == product.id,
        ).first()
        if not bought:
            return _err("You can only review products you have purchased and received")

        if Review.query.filter_by(user_id=user.id, product_id=product.id).first():
            return _err("You have already reviewed this product")

        data   = request.get_json() or {}
        rating = int(data.get("rating", 0))
        if not (1 <= rating <= 5):
            return _err("Rating must be between 1 and 5")

        review = Review(
            product_id = product.id,
            user_id    = user.id,
            rating     = rating,
            title      = data.get("title", "").strip(),
            body       = data.get("body",  "").strip(),
        )
        db.session.add(review)
        db.session.commit()
        return _ok(review.to_dict(), "Review submitted", 201)


    # =========================================================================
    # ADMIN STATS
    # =========================================================================
    @app.get("/api/admin/stats")
    @jwt_required()
    def admin_stats():
        result = _require_admin()
        if isinstance(result, tuple):
            return result

        from sqlalchemy import func
        total_users    = User.query.filter_by(role="customer").count()
        total_products = Product.query.filter_by(is_active=True).count()
        total_orders   = Order.query.count()
        total_revenue  = db.session.query(func.sum(Order.total_amount))\
                                   .filter(Order.status != "cancelled").scalar() or 0

        return _ok({
            "total_users":    total_users,
            "total_products": total_products,
            "total_orders":   total_orders,
            "total_revenue":  float(total_revenue),
        })

    # ── Error handlers ─────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(_):
        return _err("Endpoint not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(_):
        return _err("Method not allowed", 405)

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f"500 error: {e}")
        return _err("Internal server error", 500)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    env = os.environ.get("FLASK_ENV", "development")
    app = create_app(env)
    app.run(
        host  = "0.0.0.0",
        port  = int(os.environ.get("PORT", 5000)),
        debug = app.config["DEBUG"],
    )
