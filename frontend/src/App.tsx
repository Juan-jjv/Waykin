import { Route, Routes } from "react-router-dom";
import { PlanPage } from "./pages/PlanPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<PlanPage />} />
    </Routes>
  );
}
