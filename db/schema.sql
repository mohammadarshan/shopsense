CREATE TABLE users (
    id                       SERIAL PRIMARY KEY,
    email                    VARCHAR(255) UNIQUE NOT NULL,
    password_hash            VARCHAR(255) NOT NULL,
    full_name                VARCHAR(120) NOT NULL,
    role                     VARCHAR(20) NOT NULL DEFAULT 'customer'
                             CHECK (role IN ('customer', 'admin')),
    olist_customer_unique_id VARCHAR(40) UNIQUE,
    created_at               TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE products (
    id               SERIAL PRIMARY KEY,
    olist_product_id VARCHAR(40) UNIQUE,
    name             VARCHAR(200) NOT NULL,
    category         VARCHAR(100),
    description      TEXT,
    price            NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    stock            INTEGER NOT NULL DEFAULT 100 CHECK (stock >= 0),
    created_at       TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    id             SERIAL PRIMARY KEY,
    olist_order_id VARCHAR(40) UNIQUE,
    user_id        INTEGER NOT NULL REFERENCES users(id),
    status         VARCHAR(20) NOT NULL DEFAULT 'pending',
    total          NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE order_items (
    id         SERIAL PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity   INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE reviews (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    order_id   INTEGER REFERENCES orders(id),
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment    TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE cart_items (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity   INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    PRIMARY KEY (user_id, product_id)
);

CREATE INDEX idx_orders_user        ON orders(user_id);
CREATE INDEX idx_order_items_order  ON order_items(order_id);
CREATE INDEX idx_order_items_prod   ON order_items(product_id);
CREATE INDEX idx_reviews_product    ON reviews(product_id);