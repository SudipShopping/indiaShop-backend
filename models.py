"""
models.py – SQLAlchemy ORM models for IndiaShop
Tables: users, otps, categories, products, product_images,
        carts, cart_items, addresses, orders, order_items, reviews
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ─────────────────────────────────────────────────────────────────────────────
# USER
# ─────────────────────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer,     primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    phone         = db.Column(db.String(15))
    role          = db.Column(db.Enum("customer", "admin"), default="customer", nullable=False)
    is_active     = db.Column(db.Boolean, default=True)
    is_verified   = db.Column(db.Boolean, default=False)   # email OTP verified
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    addresses = db.relationship("Address",  backref="user", lazy=True, cascade="all, delete-orphan")
    cart      = db.relationship("Cart",     backref="user", uselist=False, cascade="all, delete-orphan")
    orders    = db.relationship("Order",    backref="user", lazy=True)
    reviews   = db.relationship("Review",   backref="user", lazy=True)
    otps      = db.relationship("OTP",      backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id":          self.id,
            "name":        self.name,
            "email":       self.email,
            "phone":       self.phone,
            "role":        self.role,
            "is_active":   self.is_active,
            "is_verified": self.is_verified,
            "created_at":  self.created_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# OTP  (for email verification & password reset)
# ─────────────────────────────────────────────────────────────────────────────
class OTP(db.Model):
    __tablename__ = "otps"

    id         = db.Column(db.Integer,    primary_key=True)
    user_id    = db.Column(db.Integer,    db.ForeignKey("users.id"), nullable=False)
    code       = db.Column(db.String(6),  nullable=False)
    purpose    = db.Column(db.Enum("verify_email", "reset_password"), nullable=False)
    is_used    = db.Column(db.Boolean,    default=False)
    expires_at = db.Column(db.DateTime,   nullable=False)
    created_at = db.Column(db.DateTime,   default=datetime.utcnow)

    def is_valid(self) -> bool:
        return not self.is_used and datetime.utcnow() < self.expires_at


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY
# ─────────────────────────────────────────────────────────────────────────────
class Category(db.Model):
    __tablename__ = "categories"

    id          = db.Column(db.Integer,    primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    slug        = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    emoji       = db.Column(db.String(10))   # e.g. 📱 🏠
    image_url   = db.Column(db.String(500))
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship("Product", backref="category", lazy=True)

    def to_dict(self):
        return {
            "id":          self.id,
            "name":        self.name,
            "slug":        self.slug,
            "description": self.description,
            "emoji":       self.emoji,
            "image_url":   self.image_url,
            "is_active":   self.is_active,
        }


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT
# ─────────────────────────────────────────────────────────────────────────────
class Product(db.Model):
    __tablename__ = "products"

    id           = db.Column(db.Integer,      primary_key=True)
    category_id  = db.Column(db.Integer,      db.ForeignKey("categories.id"), nullable=False)
    name         = db.Column(db.String(250),  nullable=False)
    slug         = db.Column(db.String(280),  unique=True, nullable=False, index=True)
    description  = db.Column(db.Text)
    price        = db.Column(db.Numeric(12, 2), nullable=False)
    discount_pct = db.Column(db.Integer,      default=0)       # e.g. 30 = 30% off
    stock        = db.Column(db.Integer,      default=0)
    sku          = db.Column(db.String(80),   unique=True)
    brand        = db.Column(db.String(100))
    is_active    = db.Column(db.Boolean,      default=True)
    is_featured  = db.Column(db.Boolean,      default=False)
    created_at   = db.Column(db.DateTime,     default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime,     default=datetime.utcnow, onupdate=datetime.utcnow)

    images      = db.relationship("ProductImage", backref="product", lazy=True, cascade="all, delete-orphan")
    cart_items  = db.relationship("CartItem",     backref="product", lazy=True)
    order_items = db.relationship("OrderItem",    backref="product", lazy=True)
    reviews     = db.relationship("Review",       backref="product", lazy=True, cascade="all, delete-orphan")

    @property
    def discounted_price(self) -> float:
        if self.discount_pct:
            return round(float(self.price) * (1 - self.discount_pct / 100), 2)
        return float(self.price)

    @property
    def avg_rating(self) -> float:
        if not self.reviews:
            return 0.0
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)

    @property
    def primary_image(self):
        for img in self.images:
            if img.is_primary:
                return img.url
        return self.images[0].url if self.images else None

    def to_dict(self, detail: bool = False):
        data = {
            "id":               self.id,
            "category_id":      self.category_id,
            "category_name":    self.category.name if self.category else None,
            "name":             self.name,
            "slug":             self.slug,
            "brand":            self.brand,
            "price":            float(self.price),
            "discount_pct":     self.discount_pct,
            "discounted_price": self.discounted_price,
            "stock":            self.stock,
            "is_active":        self.is_active,
            "is_featured":      self.is_featured,
            "avg_rating":       self.avg_rating,
            "review_count":     len(self.reviews),
            "primary_image":    self.primary_image,
            "images":           [img.to_dict() for img in self.images],
        }
        if detail:
            data["description"] = self.description
            data["sku"]         = self.sku
            data["reviews"]     = [r.to_dict() for r in self.reviews]
        return data


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id         = db.Column(db.Integer,    primary_key=True)
    product_id = db.Column(db.Integer,    db.ForeignKey("products.id"), nullable=False)
    url        = db.Column(db.String(500), nullable=False)
    alt_text   = db.Column(db.String(200))
    is_primary = db.Column(db.Boolean,    default=False)

    def to_dict(self):
        return {
            "id":         self.id,
            "url":        self.url,
            "alt_text":   self.alt_text,
            "is_primary": self.is_primary,
        }


# ─────────────────────────────────────────────────────────────────────────────
# ADDRESS
# ─────────────────────────────────────────────────────────────────────────────
class Address(db.Model):
    __tablename__ = "addresses"

    id         = db.Column(db.Integer,    primary_key=True)
    user_id    = db.Column(db.Integer,    db.ForeignKey("users.id"), nullable=False)
    full_name  = db.Column(db.String(150), nullable=False)
    phone      = db.Column(db.String(15), nullable=False)
    line1      = db.Column(db.String(255), nullable=False)
    line2      = db.Column(db.String(255))
    city       = db.Column(db.String(100), nullable=False)
    state      = db.Column(db.String(100), nullable=False)
    pincode    = db.Column(db.String(10),  nullable=False)
    country    = db.Column(db.String(60),  default="India")
    is_default = db.Column(db.Boolean,    default=False)

    def to_dict(self):
        return {
            "id":         self.id,
            "full_name":  self.full_name,
            "phone":      self.phone,
            "line1":      self.line1,
            "line2":      self.line2,
            "city":       self.city,
            "state":      self.state,
            "pincode":    self.pincode,
            "country":    self.country,
            "is_default": self.is_default,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CART
# ─────────────────────────────────────────────────────────────────────────────
class Cart(db.Model):
    __tablename__ = "carts"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship("CartItem", backref="cart", lazy=True, cascade="all, delete-orphan")

    @property
    def total(self) -> float:
        return round(sum(item.subtotal for item in self.items), 2)

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    def to_dict(self):
        return {
            "id":         self.id,
            "items":      [item.to_dict() for item in self.items],
            "total":      self.total,
            "item_count": self.item_count,
        }


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id         = db.Column(db.Integer, primary_key=True)
    cart_id    = db.Column(db.Integer, db.ForeignKey("carts.id"),    nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity   = db.Column(db.Integer, default=1, nullable=False)

    @property
    def subtotal(self) -> float:
        return round(self.product.discounted_price * self.quantity, 2)

    def to_dict(self):
        return {
            "id":       self.id,
            "product":  self.product.to_dict(),
            "quantity": self.quantity,
            "subtotal": self.subtotal,
        }


# ─────────────────────────────────────────────────────────────────────────────
# ORDER
# ─────────────────────────────────────────────────────────────────────────────
class Order(db.Model):
    __tablename__ = "orders"

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"),     nullable=False)
    address_id     = db.Column(db.Integer, db.ForeignKey("addresses.id"), nullable=False)
    status         = db.Column(
        db.Enum("pending", "confirmed", "shipped", "delivered", "cancelled"),
        default="pending", nullable=False
    )
    payment_method = db.Column(db.Enum("cod", "online"), default="cod",     nullable=False)
    payment_status = db.Column(db.Enum("pending", "paid", "failed", "refunded"), default="pending")
    total_amount   = db.Column(db.Numeric(12, 2), nullable=False)
    notes          = db.Column(db.Text)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items   = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")
    address = db.relationship("Address",   lazy=True)

    def to_dict(self, detail: bool = False):
        data = {
            "id":             self.id,
            "status":         self.status,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "total_amount":   float(self.total_amount),
            "created_at":     self.created_at.isoformat(),
            "updated_at":     self.updated_at.isoformat(),
        }
        if detail:
            data["items"]   = [i.to_dict() for i in self.items]
            data["address"] = self.address.to_dict() if self.address else None
            data["notes"]   = self.notes
        return data


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id         = db.Column(db.Integer,       primary_key=True)
    order_id   = db.Column(db.Integer,       db.ForeignKey("orders.id"),   nullable=False)
    product_id = db.Column(db.Integer,       db.ForeignKey("products.id"), nullable=False)
    quantity   = db.Column(db.Integer,       nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)   # locked price at order time

    @property
    def subtotal(self) -> float:
        return round(float(self.unit_price) * self.quantity, 2)

    def to_dict(self):
        return {
            "id":         self.id,
            "product":    self.product.to_dict(),
            "quantity":   self.quantity,
            "unit_price": float(self.unit_price),
            "subtotal":   self.subtotal,
        }


# ─────────────────────────────────────────────────────────────────────────────
# REVIEW
# ─────────────────────────────────────────────────────────────────────────────
class Review(db.Model):
    __tablename__ = "reviews"

    id         = db.Column(db.Integer,    primary_key=True)
    product_id = db.Column(db.Integer,    db.ForeignKey("products.id"), nullable=False)
    user_id    = db.Column(db.Integer,    db.ForeignKey("users.id"),    nullable=False)
    rating     = db.Column(db.Integer,    nullable=False)   # 1–5
    title      = db.Column(db.String(150))
    body       = db.Column(db.Text)
    created_at = db.Column(db.DateTime,   default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("product_id", "user_id", name="uq_review_user_product"),
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"),
    )

    def to_dict(self):
        return {
            "id":         self.id,
            "user_name":  self.user.name if self.user else "User",
            "rating":     self.rating,
            "title":      self.title,
            "body":       self.body,
            "created_at": self.created_at.isoformat(),
        }
