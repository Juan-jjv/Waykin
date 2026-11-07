import { BrowserRouter, Route, Routes } from "react-router-dom";
import { FamilyPage } from "./pages/FamilyPage";
import { PlanPage } from "./pages/PlanPage";
import { WalkPage } from "./pages/WalkPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PlanPage />} />
        <Route path="/walk/:id" element={<WalkPage />} />
        <Route path="/f/:id" element={<FamilyPage />} />
      </Routes>
    </BrowserRouter>
  );
}
