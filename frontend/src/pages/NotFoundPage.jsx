import { Link } from "react-router-dom";

function NotFoundPage() {
  return (
    <>
      <h1>404 - page not found</h1>
      <Link to="/">Go home</Link>
    </>
  );
}

export default NotFoundPage;