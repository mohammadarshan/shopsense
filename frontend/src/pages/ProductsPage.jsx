import { useState, useEffect } from "react";
import { Link } from "react-router-dom";

function ProductsPage() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("http://127.0.0.1:8000/products?page_size=12");
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        const data = await res.json();
        setProducts(data.items);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <p>Loading products...</p>;
  if (error) return <p className="out">Could not load products: {error}</p>;

  return (
    <>
      <h1>Shop</h1>
      <div className="cards">
        {products.map((p) => (
          <Link key={p.id} to={`/products/${p.id}`} className="card">
            <h3>{p.name}</h3>
            <p>${p.price.toFixed(2)}</p>
          </Link>
        ))}
      </div>
    </>
  );
}

export default ProductsPage;