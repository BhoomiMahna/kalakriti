import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Spinner } from "./components/ui.jsx";
import { useAuth } from "./lib/useAuth.jsx";
import { useI18n } from "./lib/i18n.jsx";
import LanguageSelect from "./pages/LanguageSelect.jsx";
import Login from "./pages/Login.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import Home from "./pages/Home.jsx";
import Products from "./pages/Products.jsx";
import Orders from "./pages/Orders.jsx";
import AddProduct from "./pages/AddProduct.jsx";
import ProductDetail from "./pages/ProductDetail.jsx";
import Profile from "./pages/Profile.jsx";
import DemoListing from "./pages/DemoListing.jsx";
import DemoInstagram from "./pages/DemoInstagram.jsx";
import InstagramAdmin from "./pages/InstagramAdmin.jsx";

function Protected({ children }) {
  const { artisan, loading } = useAuth();
  const { hasLang } = useI18n();
  const loc = useLocation();
  if (!hasLang) return <Navigate to="/language" replace />;
  if (loading)
    return (
      <div className="app-shell items-center justify-center">
        <Spinner className="h-8 w-8" />
      </div>
    );
  if (!artisan) return <Navigate to="/login" replace state={{ from: loc }} />;
  return children;
}

const P = (el) => <Protected>{el}</Protected>;

function LoginGate() {
  // Language must be chosen before login.
  const { hasLang } = useI18n();
  if (!hasLang) return <Navigate to="/language" replace />;
  return <Login />;
}

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/language" element={<LanguageSelect />} />
        <Route path="/login" element={<LoginGate />} />
        {/* Public demo pages (judges open these) */}
        <Route path="/demo/instagram/post/:externalId" element={<DemoInstagram />} />
        <Route path="/demo/:channel/product/:externalId" element={<DemoListing />} />

        <Route path="/onboarding" element={P(<Onboarding />)} />
        <Route path="/" element={P(<Home />)} />
        <Route path="/products" element={P(<Products />)} />
        <Route path="/orders" element={P(<Orders />)} />
        <Route path="/add" element={P(<AddProduct />)} />
        <Route path="/product/:id" element={P(<ProductDetail />)} />
        <Route path="/profile" element={P(<Profile />)} />
        <Route path="/instagram" element={P(<InstagramAdmin />)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
