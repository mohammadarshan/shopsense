import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";

function ProductDetailPage() {
  const { id } = useParams();
  const [product, setProduct] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      setProduct(null);
      setError(null);
      try {
        const res = await fetch(`http://127.0.0.1:8000/products/${id}`);
        if (res.status === 404) throw new Error("Product not found");
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        setProduct(await res.json());
      } catch (err) {
        setError(err.message);
      }
    }
    load();
  }, [id]);

  if (error) return <p className="out">{error}</p>;
  if (!product) return <p>Loading...</p>;

  return (
    <>
      <Link to="/products">&larr; Back to shop</Link>
      <h1>{product.name}</h1>
      <p>Category: <Link to="/products">{product.category ?? "none"}</Link></p>
      <p><strong>${product.price.toFixed(2)}</strong></p>
      <p>{product.stock > 0 ? `${product.stock} in stock` : "Sold out"}</p>
    </>
  );
}

export default ProductDetailPage;