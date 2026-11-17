import { useState, useEffect } from "react";
import "./App.css";

// 1. A component with props
function ProductCard({ name, price, inStock, onSale }) {
  return (
    <div className="card">
      <h3>{name}</h3>
      <p>${price.toFixed(2)}</p>
      {inStock ? <span className="ok">In stock</span> : <span className="out">Sold out</span>}
      {onSale ? <span className="ok">On sale</span> : <span className="out">Not on sale</span>}
    </div>
  );
}

// 2. A component with state
function Counter() {
  const [count, setCount] = useState(0);
  return (
    <p>
      <button onClick={() => setCount(count + 1)}>Clicked {count} times</button>
    </p>
  );
}

// 3. A component that talks to your API
function ApiStatus() {
  const [status, setStatus] = useState("checking...");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/health")
      .then((res) => res.json())
      .then((data) => setStatus(data.database))
      .catch(() => setStatus("unreachable"));
  }, []);

  return <p>Backend database: <strong>{status}</strong></p>;
}

// The root component
function App() {
  const products = [
    { id: 1, name: "Coffee Mug", price: 12.5, inStock: true },
    { id: 2, name: "Desk Lamp", price: 34, inStock: true },
    { id: 3, name: "Old Radio", price: 80, inStock: false },
    { id: 4, name: "Vintage Turntable", price: 150, inStock: true },
  ];

  return (
    <div className="page">
      <h1>ShopSense</h1>
      <Counter />
      <Counter />
      <ApiStatus />
      <div className="cards">
        {products.map((p) => (
          <ProductCard key={p.id} name={p.name} price={p.price} inStock={p.inStock} />
        ))}
      </div>
    </div>
  );
}

export default App;