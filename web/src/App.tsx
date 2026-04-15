import { Navigate, Route, Routes } from "react-router-dom";
import { Home } from "./pages/Home";
import { Room } from "./pages/Room";
import { Solo } from "./pages/Solo";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/room/:code" element={<Room />} />
      <Route path="/solo" element={<Solo />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
