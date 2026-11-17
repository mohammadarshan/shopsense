import { Link, NavLink } from "react-router-dom";

function Navbar() {
  return (
    <header className="navbar">
      <Link to="/" className="brand">ShopSense</Link>
      <nav>
        <NavLink to="/products">Shop</NavLink>
        <NavLink to="/cart">Cart</NavLink>
        <NavLink to="/login">Log in</NavLink>
        <NavLink to="/register">Sign up</NavLink>
        <NavLink to="/about">About</NavLink>
      </nav>
    </header>
  );
}

export default Navbar;