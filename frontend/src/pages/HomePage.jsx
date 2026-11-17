import { Link } from "react-router-dom";

function HomePage() {
  return (
    <>
      <h1>Welcome to ShopSense</h1>
      <p>Browse thousands of products, with recommendations picked for you.</p>
      <Link to="/products" className="button">Start shopping</Link>
    </>
  );
}

export default HomePage;